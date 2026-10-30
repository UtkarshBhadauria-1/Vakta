import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.classifier import IntentClassifier, RuleBasedIntentClassifier
from app.documents import chunk_documents, load_documents
from app.escalation import GRIEVANCE_ESCALATION_NOTICE, evaluate_escalation
from app.rag import NO_EVIDENCE_ANSWER, build_followup_context, build_retrieval_query, generate_answer
from app.retriever import FaissRetriever, Retriever, SentenceTransformerEmbedder
from app.schemas import ChatRequest, ChatResponse, FeedbackRequest, FeedbackResponse, SourceReference
from app.sentiment import analyze_sentiment
from app.settings import Settings, settings as default_settings
from app.telemetry import TelemetryStore

logger = logging.getLogger("vakta")


def build_retriever(config: Settings) -> FaissRetriever:
    documents = load_documents(config.data_dir)
    chunks = chunk_documents(documents)
    if not chunks:
        raise RuntimeError(f"No readable FAQ or PDF text found in {config.data_dir}")
    embedder = SentenceTransformerEmbedder(config.embedding_model)
    return FaissRetriever(chunks, embedder)


def _telemetry_opted_out(header_value: str | None) -> bool:
    return (header_value or "").strip().casefold() in {"1", "true", "yes", "on"}


def create_app(
    retriever: Retriever | None = None,
    config: Settings | None = None,
    classifier: IntentClassifier | None = None,
    telemetry: TelemetryStore | None = None,
) -> FastAPI:
    app_settings = config or default_settings

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if application.state.retriever is None:
            try:
                application.state.retriever = build_retriever(app_settings)
                logger.info("Loaded %d FAQ/PDF chunks into FAISS", len(application.state.retriever.chunks))
            except Exception:
                application.state.index_error = True
                logger.exception("Could not initialize the document retrieval index")
        yield

    application = FastAPI(
        title="Vakta API",
        description="Evidence-grounded university student support using FAISS, Sentence Transformers, and Groq.",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.retriever = retriever
    application.state.settings = app_settings
    application.state.index_error = False
    application.state.classifier = classifier or RuleBasedIntentClassifier()
    application.state.telemetry = telemetry or TelemetryStore()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Telemetry-Opt-Out"],
    )

    @application.get("/api/health")
    async def health(request: Request) -> dict[str, object]:
        current_retriever = request.app.state.retriever
        chunks = getattr(current_retriever, "chunks", []) if current_retriever else []
        return {
            "status": "ok" if current_retriever else "degraded",
            "retrieval_ready": current_retriever is not None,
            "chunks_loaded": len(chunks),
            "groq_configured": bool(app_settings.groq_api_key),
            "intent_classifier_ready": True,
            "telemetry_records_count": len(request.app.state.telemetry.get_records()),
        }

    @application.post("/api/chat", response_model=ChatResponse)
    async def chat(
        payload: ChatRequest,
        request: Request,
        x_telemetry_opt_out: str | None = Header(default=None, alias="X-Telemetry-Opt-Out"),
    ) -> ChatResponse:
        current_retriever = request.app.state.retriever
        if current_retriever is None:
            raise HTTPException(status_code=503, detail="The document index is not ready. Check backend logs and retry.")

        intent_classifier: IntentClassifier = request.app.state.classifier
        intent_result = intent_classifier.classify(payload.question)
        sentiment = analyze_sentiment(payload.question)

        retrieval_query = build_retrieval_query(payload.question, payload.conversation)
        results = current_retriever.search(retrieval_query, top_k=app_settings.top_k)
        evidence = [result for result in results if result.score >= app_settings.min_relevance_score]
        decision = evaluate_escalation(
            question=payload.question,
            intent=intent_result.intent,
            confidence_score=intent_result.confidence,
            evidence_count=len(evidence),
            sentiment_label=sentiment.label,
        )

        telemetry_enabled = not _telemetry_opted_out(x_telemetry_opt_out)
        telemetry: TelemetryStore = request.app.state.telemetry
        session_id: str | None = None
        if telemetry_enabled:
            session_id = payload.session_id or telemetry.generate_session_id()
            telemetry.record(
                session_id=session_id,
                user_query_type=intent_result.query_type,
                intent=intent_result.intent,
                confidence_score=intent_result.confidence,
                escalated=1 if decision.escalated else 0,
                user_rating=None,
            )

        common = {
            "session_id": session_id,
            "intent": intent_result.intent,
            "confidence_score": intent_result.confidence,
            "user_query_type": intent_result.query_type,
            "escalated": decision.escalated,
            "escalation_reason": decision.escalation_reason,
            "requires_clarification": decision.requires_clarification,
            "sentiment_label": sentiment.label,
            "sentiment_score": sentiment.score,
        }

        if decision.priority_rule == "rule_a_explicit_request":
            return ChatResponse(
                answer=decision.suggested_answer or "",
                sources=[],
                used_context=False,
                **common,
            )

        if not evidence:
            answer = decision.suggested_answer or NO_EVIDENCE_ANSWER
            return ChatResponse(answer=answer, sources=[], used_context=False, **common)

        api_key = (app_settings.groq_api_key or "").strip()
        if not api_key:
            raise HTTPException(
                status_code=503,
                detail="Answer generation is not configured. Set GROQ_API_KEY in the backend environment.",
            )
        try:
            answer = await run_in_threadpool(
                generate_answer,
                payload.question,
                evidence,
                app_settings.groq_model,
                api_key,
                build_followup_context(payload.conversation),
                sentiment.label,
            )
        except Exception:
            # Do not log provider exception text, request content, or credential-bearing details.
            logger.warning("Groq answer generation failed; provider details suppressed")
            raise HTTPException(
                status_code=502,
                detail="The answer service is temporarily unavailable. Please try again.",
            ) from None

        sources = [
            SourceReference(
                id=result.chunk.chunk_id,
                title=result.chunk.title,
                source=result.chunk.source,
                excerpt=result.chunk.text[:360],
                score=round(result.score, 4),
                page=result.chunk.page,
            )
            for result in evidence
        ]
        if not answer.strip():
            raise HTTPException(status_code=502, detail="The answer service returned an empty response.")
        if decision.priority_rule == "rule_b_grievance_intent":
            answer = answer.strip() + GRIEVANCE_ESCALATION_NOTICE

        return ChatResponse(answer=answer.strip(), sources=sources, used_context=True, **common)

    @application.post("/api/feedback", response_model=FeedbackResponse)
    async def submit_feedback(
        payload: FeedbackRequest,
        request: Request,
        x_telemetry_opt_out: str | None = Header(default=None, alias="X-Telemetry-Opt-Out"),
    ) -> FeedbackResponse:
        if _telemetry_opted_out(x_telemetry_opt_out):
            return FeedbackResponse(
                success=True,
                session_id=payload.session_id,
                user_rating=payload.user_rating,
                message="Feedback was not recorded because session analytics are disabled.",
            )

        telemetry: TelemetryStore = request.app.state.telemetry
        updated_record = telemetry.update_rating(session_id=payload.session_id, user_rating=payload.user_rating)
        if updated_record is None:
            raise HTTPException(status_code=404, detail=f"Session '{payload.session_id}' not found.")
        return FeedbackResponse(
            success=True,
            session_id=payload.session_id,
            user_rating=payload.user_rating,
            message="Feedback recorded successfully.",
        )

    return application


app = create_app()
