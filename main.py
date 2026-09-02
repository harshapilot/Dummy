"""
Travel Planner - FastAPI Application & REST API Layer
=====================================================
INTERVIEW EXPLANATION:
----------------------
This file exposes the stateful multi-agent LangGraph workflow over a production-grade
REST API using FastAPI.

Key Architectural Highlights for Interviewers:
1. Thread-Id Partitioning:
   - Each trip request is assigned a unique UUID (`plan_id`).
   - In LangGraph, execution state is partitioned by `thread_id`:
     `config = {"configurable": {"thread_id": plan_id}}`.
   - All subsequent read, update, and resume operations target this specific thread_id.
2. Non-blocking Breakpoint Resume:
   - When a plan is created, execution runs through Nodes 1, 2, and 3, then halts
     at `hitl_review_node` due to `interrupt_before`.
   - The thread snapshot is stored in the checkpointer (`MemorySaver`).
   - The user/client queries `GET /plan/{id}` to view the draft itinerary and research data.
   - When the user reviews the draft, `POST /plan/{id}/review` updates the thread state
     (`workflow.update_state(...)`) and resumes graph execution (`workflow.invoke(None, config)`).
   - Passing `None` as the first argument to `invoke` instructs LangGraph to resume from
     the paused breakpoint using the existing thread state!
3. Robust Error Handling & Defensive HTTP Status Codes:
   - HTTP 201 Created for plan initiation.
   - HTTP 404 Not Found if an invalid plan_id is passed.
   - HTTP 400 Bad Request if trying to review a plan that is not paused or fetching
     final before approval.
   - HTTP 500 Internal Server Error with centralized logging on unhandled runtime failures.
"""

from fastapi import FastAPI, HTTPException, Path, status
from fastapi.responses import RedirectResponse
import uuid
import logging

# Pydantic Schemas for input validation and strict serialization
from travel_planner.app.models.schemas import (
    PlanRequest,
    PlanResponse,
    ReviewRequest,
    PlanStatusResponse,
    FinalPlanResponse,
)
# Pre-compiled singleton LangGraph workflow
from travel_planner.app.graph.workflow import travel_planner_workflow

# Configure structured application-level logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI application instance
app = FastAPI(
    title="AI Travel Planner API",
    description="A multi-agent stateful travel planner using LangGraph and FastAPI with Human-in-the-Loop approval.",
    version="1.0.0"
)


# -----------------------------------------------------------------------------
# ROOT REDIRECT
# -----------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def redirect_to_docs():
    """
    Convenience route: Redirects root '/' traffic to the interactive OpenAPI /docs.
    Excluded from OpenAPI schema documentation to keep the API documentation clean.
    """
    return RedirectResponse(url="/docs")


# -----------------------------------------------------------------------------
# ENDPOINT 1: CREATE A NEW TRAVEL PLAN (START WORKFLOW UP TO BREAKPOINT)
# -----------------------------------------------------------------------------
@app.post("/plan", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(request: PlanRequest):
    """
    Step 1: Initiates a new travel planning session.
    
    Execution Flow:
    1. Generates a new UUID `plan_id` to act as the LangGraph `thread_id`.
    2. Builds the initial state dictionary matching `TravelPlanState`.
    3. Calls `travel_planner_workflow.invoke(initial_state, config)`:
       - Runs orchestrator_input -> research_agent -> planner_agent.
       - Automatically pauses before `hitl_review_node`.
    4. Retrieves the latest snapshot with `get_state(config)` and confirms pause state.
    5. Returns `plan_id` and `status="pending_review"` to client.
    """
    # Generate unique session thread ID
    plan_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": plan_id}}
    
    # Initialize the state schema values
    initial_state = {
        "destination": request.destination,
        "travel_dates": request.travel_dates,
        "budget_range": request.budget_range,
        "travelers_count": request.travelers_count,
        "interests": request.interests,
        "research_data": {},
        "draft_itinerary": "",
        "user_feedback": "",
        "feedback_status": "",
        "status": "started"
    }
    
    logger.info(f"[API: /plan] Starting planning workflow for plan_id={plan_id} -> {request.destination}")
    
    try:
        # Invoke workflow: runs until reaching compile-time breakpoint (interrupt_before)
        travel_planner_workflow.invoke(initial_state, config)
        
        # Read thread state snapshot from checkpointer
        state_snapshot = travel_planner_workflow.get_state(config)
        
        # In LangGraph, state_snapshot.next contains the tuple of nodes waiting to run next.
        # If 'hitl_review_node' is pending, the graph is successfully paused at the breakpoint!
        is_paused = len(state_snapshot.next) > 0 and "hitl_review_node" in state_snapshot.next[0]
        
        return PlanResponse(
            plan_id=plan_id,
            status="pending_review" if is_paused else "started"
        )
    except Exception as e:
        logger.exception(f"[API: /plan] Error starting workflow for plan_id={plan_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize travel plan: {str(e)}"
        )


# -----------------------------------------------------------------------------
# ENDPOINT 2: GET PLAN STATUS & INSPECT STATE SNAPSHOT
# -----------------------------------------------------------------------------
@app.get("/plan/{id}", response_model=PlanStatusResponse)
def get_plan_status(id: str = Path(..., description="The unique plan ID")):
    """
    Step 2: Inspects the current state of an ongoing or completed travel plan.
    
    Execution Flow:
    1. Reconstructs thread config using `{id}`.
    2. Calls `travel_planner_workflow.get_state(config)`:
       - If no values exist, returns HTTP 404 (Plan not found).
    3. Reads all channels: destination, weather data, web search brief, draft itinerary,
       and HITL feedback status.
    4. Enables UI/client to display the draft itinerary and external research to the user.
    """
    config = {"configurable": {"thread_id": id}}
    state_snapshot = travel_planner_workflow.get_state(config)
    
    # If the checkpointer has no recorded state for this thread ID, return 404
    if not state_snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Travel plan with ID '{id}' was not found in active state checkpointer."
        )
        
    values = state_snapshot.values
    # Check if currently paused at the review breakpoint
    is_paused = len(state_snapshot.next) > 0 and "hitl_review_node" in state_snapshot.next[0]
    current_status = "pending_review" if is_paused else values.get("status", "unknown")
    
    return PlanStatusResponse(
        plan_id=id,
        status=current_status,
        destination=values.get("destination", ""),
        travel_dates=values.get("travel_dates", ""),
        budget_range=values.get("budget_range", ""),
        travelers_count=values.get("travelers_count", 1),
        interests=values.get("interests", []),
        research_data=values.get("research_data"),
        draft_itinerary=values.get("draft_itinerary"),
        user_feedback=values.get("user_feedback"),
        feedback_status=values.get("feedback_status")
    )


# -----------------------------------------------------------------------------
# ENDPOINT 3: SUBMIT HUMAN REVIEW & RESUME WORKFLOW (HITL)
# -----------------------------------------------------------------------------
@app.post("/plan/{id}/review", response_model=PlanResponse)
def submit_plan_review(
    id: str = Path(..., description="The unique plan ID"),
    review: ReviewRequest = None
):
    """
    Step 3: Injects user review feedback and resumes the paused LangGraph workflow.
    
    Execution Flow:
    1. Validates that payload exists and plan exists.
    2. Validates that the graph is actually paused at `hitl_review_node`.
       (Prevents invalid state transitions if already completed or still processing).
    3. Calls `travel_planner_workflow.update_state(config, {...})`:
       - Injects `user_feedback` (comments) and `feedback_status` ('approve'|'modify'|'reject').
    4. Calls `travel_planner_workflow.invoke(None, config)`:
       - Resumes execution from `hitl_review_node`.
       - If 'approve': transitions through `finalizer_node` -> `END`.
       - If 'modify': smart classifier routes back to `research_agent` or `planner_agent`,
         then re-enters `hitl_review_node` breakpoint for another inspection!
    """
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review payload is required."
        )
        
    config = {"configurable": {"thread_id": id}}
    state_snapshot = travel_planner_workflow.get_state(config)
    
    # Check plan existence
    if not state_snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Travel plan with ID '{id}' not found."
        )
        
    # Verify the workflow is currently halted at the HITL breakpoint
    if len(state_snapshot.next) == 0 or "hitl_review_node" not in state_snapshot.next[0]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Travel plan '{id}' is not awaiting review. Current status: '{state_snapshot.values.get('status')}'."
        )
        
    logger.info(f"[API: /plan/{id}/review] Submitting review: Action={review.action}, Feedback='{review.feedback}'")
    
    try:
        # Step A: Mutate state with user feedback
        travel_planner_workflow.update_state(
            config,
            {
                "user_feedback": review.feedback,
                "feedback_status": review.action
            }
        )
        
        # Step B: Resume graph execution from current breakpoint
        # Passing None signals LangGraph to continue with existing state
        travel_planner_workflow.invoke(None, config)
        
        # Step C: Inspect post-resumption status
        new_state_snapshot = travel_planner_workflow.get_state(config)
        new_paused = len(new_state_snapshot.next) > 0 and "hitl_review_node" in new_state_snapshot.next[0]
        new_status = "pending_review" if new_paused else new_state_snapshot.values.get("status", "unknown")
        
        return PlanResponse(
            plan_id=id,
            status=new_status
        )
    except Exception as e:
        logger.exception(f"[API: /plan/{id}/review] Error processing review for plan_id={id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit review and resume planning: {str(e)}"
        )


# -----------------------------------------------------------------------------
# ENDPOINT 4: GET FINALIZED TRIP PLAN
# -----------------------------------------------------------------------------
@app.get("/plan/{id}/final", response_model=FinalPlanResponse)
def get_final_plan(id: str = Path(..., description="The unique plan ID")):
    """
    Step 4: Retrieves the finalized trip package once approved.
    
    Execution Flow:
    1. Reconstructs thread config for `{id}` and fetches snapshot.
    2. Validates that status == 'completed'. If not, returns HTTP 400 Bad Request
       explaining that user must approve the plan first.
    3. Returns the final, polished travel itinerary with confirmed budget calculations.
    """
    config = {"configurable": {"thread_id": id}}
    state_snapshot = travel_planner_workflow.get_state(config)
    
    if not state_snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Travel plan with ID '{id}' not found."
        )
        
    values = state_snapshot.values
    current_status = values.get("status", "")
    
    # Defensive guard: Ensure plan was reviewed and finalized before serving
    if current_status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Travel plan is not finalized. Current status: '{current_status}'. Please review and approve the draft plan first."
        )
        
    return FinalPlanResponse(
        plan_id=id,
        final_itinerary=values.get("draft_itinerary", "")
    )

