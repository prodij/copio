from fastapi import APIRouter

from copio_api.api.v1 import auth, capabilities, chat, inngest, reactions, threads

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(threads.router, prefix="/threads", tags=["threads"])
api_router.include_router(reactions.router, prefix="/reactions", tags=["reactions"])
api_router.include_router(capabilities.router, prefix="/capabilities", tags=["capabilities"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Inngest's serve() registers its own /api/inngest path on the router it's
# given — mount that router at the app root, not under /api/v1.
inngest_router = inngest.router
