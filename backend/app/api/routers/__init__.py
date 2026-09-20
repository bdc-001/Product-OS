from fastapi import APIRouter
from app.api.routers.marketing import router as marketing_router

from app.api.routers.artifacts import router as artifacts_router
from app.api.routers.cards import router as cards_router
from app.api.routers.cliq import router as cliq_router
from app.api.routers.codebase import router as codebase_router
from app.api.routers.comms import router as comms_router
from app.api.routers.competitors import router as competitors_router
from app.api.routers.copilot import router as copilot_router
from app.api.routers.insights import router as insights_router
from app.api.routers.issues import router as issues_router
from app.api.routers.platform import router as platform_router
from app.api.routers.prd import router as prd_router
from app.api.routers.release_asks import router as release_asks_router
from app.api.routers.roadmap import router as roadmap_router
from app.api.routers.standup import router as standup_router

from app.api.routers.knowledge import router as knowledge_router
from app.api.routers.prototypes import router as prototypes_router

router = APIRouter()
for _sub in (
    marketing_router,
    knowledge_router,
    platform_router,
    standup_router,
    issues_router,
    cards_router,
    cliq_router,
    insights_router,
    codebase_router,
    prd_router,
    comms_router,
    artifacts_router,
    roadmap_router,
    copilot_router,
    release_asks_router,
    competitors_router,
    prototypes_router,
):
    router.include_router(_sub)
