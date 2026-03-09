from fastapi import APIRouter, HTTPException

from app.routes import workflow as workflow_route

router = APIRouter()


@router.get("/final-bundle/{run_id}")
async def get_final_bundle(run_id: str):
    try:
        final_bundle = await workflow_route.coordinator.get_final_bundle_status(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "status": "success",
        "run_id": run_id,
        "final_bundle": final_bundle,
        "message": "Final bundle metadata is available. To download a zip archive, call POST /api/final-bundle/export with the current scenes.",
    }
