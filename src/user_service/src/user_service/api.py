import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import bcrypt
from fastapi import (
    Body,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from PIL import Image, ImageOps
from pydantic import BaseModel

from admin.main import ui

from .analytics.redis import get_redis, is_active, mark_event
from .models.auth import AuthRepository, get_auth_repository
from .models.friends import FriendshipRepository, get_friendship_repository
from .models.session_analytics import SessionAnalyticsRepository, get_session_analytics_repository
from .models.user import UserRepository, UserSchema, get_user_repository

logger = logging.getLogger("uvicorn.error")
app = FastAPI()
# app.include_router(analytics_router)



AVATAR_DIR = Path("avatars")
AVATAR_DIR.mkdir(exist_ok=True)
MAX_SIZE = (256, 256)
AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


# Response Model
class UserPublic(BaseModel):
    id: int
    name: str
    email: str
   


# Request Models
class AuthModel(BaseModel):
    user_id: int
    password: Optional[str] = None
    jwt: Optional[str] = None


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    new_password: Optional[str] = None
    auth: Optional[AuthModel] = None


class FriendRequestPublic(BaseModel):
    requestor: int
    requestee: int
    date_time: datetime


class FriendRequestModel(BaseModel):
    requestor: Optional[int] = None
    requestee: Optional[int] = None
    auth: Optional[AuthModel] = None


class FriendRequestAnswer(BaseModel):
    decision: str
    auth: Optional[AuthModel] = None


class AuthRequest(BaseModel):
    id: int
    password: str
    expiry: str


async def validate_user_exists(id: int, user_repo: UserRepository):
    user = await user_repo.get_by_id(id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")


def validate_avatar_exists(id: int) -> Path:
    path = AVATAR_DIR / f"{id}.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Avatar not found")
    return path


def validate_avatar_does_not_exist(id: int) -> Path:
    path = AVATAR_DIR / f"{id}.jpg"
    if path.exists():
        raise HTTPException(status_code=409, detail="Avatar already exists")
    return path


def validate_image_file(file: UploadFile):
    extension = Path(file.filename).suffix.lower()
    if not file.filename or extension not in AVATAR_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")


async def save_avatar(file: UploadFile, avatar_path: Path):
    temp_path = avatar_path.with_suffix(".tmp")
    with temp_path.open("wb") as buffer:
        buffer.write(await file.read())

    with Image.open(temp_path) as img:
        img = img.convert("RGB")
        img = ImageOps.fit(img, MAX_SIZE, Image.Resampling.LANCZOS)
        img.save(avatar_path, format="JPEG", quality=85)

    temp_path.unlink()




# -------------- V2 --------------


@app.get("/v2/users/")
async def list_users_v2(request: Request, user_repo: UserRepository = Depends(get_user_repository)):

    user_models = await user_repo.get_all()
    return {
        "users": [
            UserPublic(
                id=m.id,
                name=m.name,
                email=m.email,
            )
            for m in user_models
        ]
    }


@app.get("/v2/users/name/{name:str}")
async def get_user_by_name_v2(
    name: str, request: Request, user_repo: UserRepository = Depends(get_user_repository)
):
    
    user = await user_repo.get_by_name(name)
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")
    return {"user": UserPublic(id=user.id, name=user.name, email=user.email)}


@app.get("/v2/users/id/{id:int}")
async def get_user_by_id_v2(
    id: int,
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository),
):


    user = await user_repo.get_by_id(id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")
    return {"user": UserPublic(id=user.id, name=user.name, email=user.email)}


@app.post("/v2/users/", status_code=201, response_model=UserPublic)
async def create_user_v2(
    user: UserCreate, user_repo: UserRepository = Depends(get_user_repository)
):
    new_user = await user_repo.create(user.name, user.email, user.password)
    if new_user is None:
        raise HTTPException(status_code=409, detail="User or email already exists")
    else:
        return UserPublic(
            id=new_user.id, name=new_user.name, email=new_user.email
        )


@app.put("/v2/users/{id:int}", status_code=201, response_model=UserPublic)
async def update_user_v2(
    id: int,
    request: Request,
    request_model: UserUpdate,
    user_repo: UserRepository = Depends(get_user_repository),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    sess_repo: SessionAnalyticsRepository = Depends(get_session_analytics_repository),
):
    user = await user_repo.get_by_id(id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found!")

    auth = request_model.auth
    if not await authenticate(auth, user_repo, auth_repo):
        raise HTTPException(status_code=401, detail="Unauthorized!")

    # authenticated_user = await user_repo.get_by_id(auth.user_id)
    

    if auth.password or request_model.new_password:
        # Left a field empty
        if not (auth.password and request_model.new_password):
            raise HTTPException(status_code=400, detail="Must enter password and new password!")
        success = await user_repo.change_password(id, auth.password, request_model.new_password)
        if not success:
            raise HTTPException(status_code=400, detail="Incorrect password!")

    fields_to_update = {}

    if request_model.name:
        fields_to_update["name"] = request_model.name
    if request_model.email:
        fields_to_update["email"] = request_model.email

    if fields_to_update is not None:
        user = await user_repo.update_user(id, **fields_to_update)

    return UserPublic(id=user.id, name=user.name, email=user.email)


@app.delete("/v2/users/{id}", status_code=202)
async def delete_user_v2(
    id: int,
    auth: AuthModel,
    user_repo: UserRepository = Depends(get_user_repository),
    auth_repo: AuthRepository = Depends(get_auth_repository),
):
    user = await user_repo.get_by_id(id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")

    if not await authenticate(auth, user_repo, auth_repo):
        raise HTTPException(status_code=401, detail="Unauthorized!")

    success = await user_repo.delete_by_id(user.id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found!")

    return {"detail": f"User with id {user.id} deleted!"}


@app.get("/v2/users/{id}/avatar")
async def get_avatar_v2(id: int, user_repo: UserRepository = Depends(get_user_repository)):
    await validate_user_exists(id, user_repo)

    avatar_path = validate_avatar_exists(id)
    return FileResponse(avatar_path)


@app.post("/v2/users/{id}/avatar")
async def create_avatar_v2(
    id: int,
    file: UploadFile = File(...),
    auth: str = Form(...),
    user_repo: UserRepository = Depends(get_user_repository),
    auth_repo: AuthRepository = Depends(get_auth_repository),
):
    auth = AuthModel(**json.loads(auth))
    await validate_user_exists(id, user_repo)
    if not auth or not await authenticate(auth, user_repo, auth_repo):
        raise HTTPException(status_code=401, detail="Unauthorized")

    avatar_path = validate_avatar_does_not_exist(id)
    validate_image_file(file)
    await save_avatar(file, avatar_path)
    return {"detail": "Avatar created"}


@app.put("/v2/users/{id}/avatar")
async def update_avatar_v2(
    id: int,
    file: UploadFile = File(...),
    auth: str = Form(...),
    user_repo: UserRepository = Depends(get_user_repository),
    auth_repo: AuthRepository = Depends(get_auth_repository),
):
    auth = AuthModel(**json.loads(auth))
    await validate_user_exists(id, user_repo)

    if not await authenticate(auth, user_repo, auth_repo):
        raise HTTPException(status_code=401, detail="Unauthorized")

    avatar_path = validate_avatar_exists(id)
    validate_image_file(file)
    await save_avatar(file, avatar_path)
    return {"detail": "Avatar updated"}


@app.delete("/v2/users/{id}/avatar")
async def delete_avatar_v2(
    id: int,
    auth: str = Form(...),
    user_repo: UserRepository = Depends(get_user_repository),
    auth_repo: AuthRepository = Depends(get_auth_repository),
):
    auth = AuthModel(**json.loads(auth))
    if not await authenticate(auth, user_repo, auth_repo):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if auth.user_id != id:
        raise HTTPException(status_code=403, detail="You can only delete your own avatar")

    await validate_user_exists(id, user_repo)
    avatar_path = validate_avatar_exists(id)
    avatar_path.unlink()
    return {"detail": "Avatar deleted"}


@app.get("/v2/analytics")
async def get_analytics(
    on: date | None = None,
    since: date | None = None,
    session_analytics_repo: SessionAnalyticsRepository = Depends(get_session_analytics_repository),
):
    session_length = {
        "min": timedelta(),
        "max": timedelta(),
        "mean": timedelta(),
        "median": timedelta(),
        "p95": timedelta(),
    }
    active_users = {
        "current": 0,
        "max": 0,
    }

    if since:  # Average the stats for the number of days since the given date
        days = (date.today() - since).days
        for day in range(days):
            curr_date = since + timedelta(days=day)
            session_length["min"] += await session_analytics_repo.min_session_length(curr_date)
            session_length["max"] += await session_analytics_repo.max_session_length(curr_date)
            session_length["mean"] += await session_analytics_repo.mean_session_length(curr_date)
            session_length["median"] += await session_analytics_repo.median_session_length(
                curr_date
            )
            session_length["p95"] += await session_analytics_repo.percentile_session_length(
                95, curr_date
            )
            active_users["current"] += await session_analytics_repo.get_current_active_users(
                curr_date
            )
            active_users["max"] += await session_analytics_repo.get_max_active_users(curr_date)
        for k, v in session_length.items():
            session_length[k] /= 10
        for k, v in active_users.items():
            active_users[k] /= 10
    else:
        session_length = {
            "min": await session_analytics_repo.min_session_length(on),
            "max": await session_analytics_repo.max_session_length(on),
            "mean": await session_analytics_repo.mean_session_length(on),
            "median": await session_analytics_repo.median_session_length(on),
            "p95": await session_analytics_repo.percentile_session_length(95, on),
        }
        active_users = {
            "current": await session_analytics_repo.get_current_active_users(on),
            "max": await session_analytics_repo.get_max_active_users(on),
        }

    return {"session_length": session_length, "active_users": active_users}


@app.post("/v2/authentications")
async def create_authentication(
    request: AuthRequest,
    user_repo: UserRepository = Depends(get_user_repository),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    sess_repo: SessionAnalyticsRepository = Depends(get_session_analytics_repository),
    r=Depends(get_redis),
):
    expiry = datetime.strptime(request.expiry, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

    # Verify that the user's password is correct
    user = await user_repo.get_by_id(request.id)
    if not bcrypt.checkpw(request.password.encode(), user.password):
        raise HTTPException(status_code=400, detail="Invalid password!")

    # Create a web token using the given id and expiry
    token = await auth_repo.create(request.id, expiry)

    # Verify that the token was generated successfully
    if token is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid expiry! Expiry time must be some time within the next hour.",
        )

    # checks if active on redis, if so we update_session else create session and set as active
    if await is_active(user.id, r):
        await sess_repo.update_user_session(user)
    else:
        await sess_repo.create(user)
        await mark_event(user.id, r)

    return {"jwt": token}


@app.delete("/v2/authentications")
async def delete_authentication(
    jwt: str = Body(..., embed=True),
    auth_repo: AuthRepository = Depends(get_auth_repository),
):
    await auth_repo.delete_by_token(jwt)

    return {"detail": "Token deleted."}


async def authenticate(
    auth: AuthModel,
    user_repo: UserRepository,
    auth_repo: AuthRepository,
) -> bool:
    """
    Checks the validity of one or both of the given password/jwt
    """
    pw_auth = False
    jwt_auth = False
    if not auth:
        return False
    if auth.password:
        # Verify that the user's password is correct
        user = await user_repo.get_by_id(auth.user_id)
        if not bcrypt.checkpw(auth.password.encode(), user.password):
            pw_auth = False
        else:  # pw correct, so skip checking the jwt
            return True
    if auth.jwt:
        jwt_auth = await auth_repo.validate(auth.jwt)

    return pw_auth | jwt_auth


"""User Friend requests and User Friends"""


@app.get("/v2/users/{user_id}/friend-requests/")
async def get_friend_requests_v2(
    user_id: int,
    q: Optional[str] = None,  # ?q=incoming | ?q=outgoing
    user_repo: UserRepository = Depends(get_user_repository),
    friends_repo: FriendshipRepository = Depends(get_friendship_repository),
    sess_repo: SessionAnalyticsRepository = Depends(get_session_analytics_repository),
    r=Depends(get_redis),
):
    await validate_user_exists(user_id, user_repo)

    user = await user_repo.get_by_id(user_id)

    if q not in {"incoming", "outgoing"}:
        raise HTTPException(
            status_code=400, detail="Unsupported query. Use q=incoming or q=outgoing"
        )

    if q == "incoming":
        requests = await friends_repo.get_requests(user_id)
    else:  # q == "outgoing"
        requests = await friends_repo.get_unanswered_requests(user_id)

    payload: List[FriendRequestPublic] = [
        FriendRequestPublic(from_=r.requestor_id, to=r.requestee_id) for r in requests
    ]

    # checks if active on redis, if so we update_session else create session and set as active
    if await is_active(user.id, r):
        await sess_repo.update_user_session(user)
    else:
        await sess_repo.create(user)
        await mark_event(user.id, r)

    return {"requests": payload}


@app.post("/v2/users/{receiver_id}/friend-requests/")
async def create_friend_request_v2(
    receiver_id: int,
    request: FriendRequestModel,
    user_repo: UserRepository = Depends(get_user_repository),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    friendship_repo: FriendshipRepository = Depends(get_friendship_repository),
    sess_repo: SessionAnalyticsRepository = Depends(get_session_analytics_repository),
    r=Depends(get_redis),
):
    auth = request.auth
    if not await authenticate(auth, user_repo, auth_repo):
        raise HTTPException(status_code=401, detail="Unauthorized!")

    sender_id = request.requestor
    if sender_id == receiver_id:
        raise HTTPException(status_code=400, detail="Can't send a friend request to yourself.")

    receiver = await user_repo.get_by_id(receiver_id)
    if receiver is None:
        raise HTTPException(status_code=404, detail="User not found.")

    existing_friendship = await friendship_repo.get_friendship_status(
        sender_id, receiver_id, "accepted"
    )
    if existing_friendship:
        raise HTTPException(status_code=400, detail="You are already friends.")

    pending = await friendship_repo.get_friendship_status(sender_id, receiver_id, "pending")
    if pending:
        who = "them" if pending.requestor_id == receiver_id else "you"
        raise HTTPException(status_code=400, detail=f"A pending request already exists from {who}.")

    req = await friendship_repo.send_request(sender_id, receiver_id)

    sender = await user_repo.get_by_id(sender_id)

    # checks if active on redis, if so we update_session else create session and set as active
    if await is_active(sender.id, r):
        await sess_repo.update_user_session(sender)
    else:
        await sess_repo.create(sender)
        await mark_event(sender.id, r)

    return {
        "request_id": req.id,
        "sender_id": req.requestor_id,
        "receiver_id": req.requestee_id,
        "status": req.status,
        "message": f"Friend request sent to {receiver.name}.",
    }


@app.put("/v2/users/{user_id}/friend-requests/{other_id}", status_code=200)
async def answer_friend_request_v2(
    user_id: int,
    other_id: int,
    request: FriendRequestAnswer,
    user_repo: UserRepository = Depends(get_user_repository),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    friendship_repo: FriendshipRepository = Depends(get_friendship_repository),
    sess_repo: SessionAnalyticsRepository = Depends(get_session_analytics_repository),
    r=Depends(get_redis),
):
    auth = request.auth
    decision = request.decision
    if not await authenticate(auth, user_repo, auth_repo):
        raise HTTPException(status_code=401, detail="Unauthorized!")

    if auth.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your request to answer."
        )

    await validate_user_exists(user_id, user_repo)
    await validate_user_exists(other_id, user_repo)

    req = await friendship_repo.get_friendship_status(other_id, user_id, "pending")
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No pending request from this user."
        )

    if decision == "accept":
        await friendship_repo.accept_request(req.id)
        return {
            "detail": "Friend request accepted.",
            "friendship": {"user_id": user_id, "other_id": other_id},
        }
    user = await user_repo.get_by_id(auth.user_id)

    # checks if active on redis, if so we update_session else create session and set as active
    if user is not None:
        if await is_active(user.id, r):
            await sess_repo.update_user_session(user)
        else:
            await sess_repo.create(user)
            await mark_event(user.id, r)

    await friendship_repo.delete_friendship(other_id, user_id)
    return {"detail": "Friend request declined."}


@app.delete("/v2/users/{user_id}/friend-requests/{other_id}", status_code=202)
async def cancel_friend_request_v2(
    user_id: int,
    other_id: int,
    auth: AuthModel | None = None,
    user_repo: UserRepository = Depends(get_user_repository),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    friendship_repo: FriendshipRepository = Depends(get_friendship_repository),
    sess_repo: SessionAnalyticsRepository = Depends(get_session_analytics_repository),
    r=Depends(get_redis),
):
    if not await authenticate(auth, user_repo, auth_repo):
        raise HTTPException(status_code=401, detail="Unauthorized!")

    if auth.user_id != other_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only cancel your own outgoing friend requests.",
        )

    await validate_user_exists(user_id, user_repo)
    await validate_user_exists(other_id, user_repo)

    request = await friendship_repo.get_friendship_status(user_id, other_id, "pending")
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending friend request found to cancel.",
        )

    other_user = await user_repo.get_by_id(other_id)

    # checks if active on redis, if so we update_session else create session and set as active
    if await is_active(other_user.id, r):
        await sess_repo.update_user_session(other_user)
    else:
        await sess_repo.create(other_id)
        await mark_event(other_user.id, r)

    await friendship_repo.delete_friendship(user_id, other_id)
    return {"detail": f"Friend request to user {user_id} has been cancelled."}


@app.get("/v2/users/{user_id}/friends/")
async def list_friends_v2(
    user_id: int,
    user_repo: UserRepository = Depends(get_user_repository),
    friends_repo: FriendshipRepository = Depends(get_friendship_repository),
    sess_repo: SessionAnalyticsRepository = Depends(get_session_analytics_repository),
    r=Depends(get_redis),
):
    await validate_user_exists(user_id, user_repo)
    friends = await friends_repo.list_friends(user_id)
    payload: List[UserPublic] = [
        UserPublic(id=f.id, name=f.name, email=f.email) for f in friends
    ]

    user = await user_repo.get_by_id(user_id)

    # checks if active on redis, if so we update_session else create session and set as active
    if await is_active(user_id, r):
        await sess_repo.update_user_session(user)
    else:
        await sess_repo.create(user_id)
        await mark_event(user_id, r)

    return {"friends": payload}


@app.get("/v2/users/{user_id}/friends/name/{friend_name}")
async def get_friend_by_name_v2(
    user_id: int,
    friend_name: str,
    user_repo: UserRepository = Depends(get_user_repository),
    friends_repo: FriendshipRepository = Depends(get_friendship_repository),
):
    await validate_user_exists(user_id, user_repo)
    friend = await friends_repo.get_friend_by_name(user_id, friend_name)
    if not friend:
        raise HTTPException(status_code=404, detail="Friend not found.")
    return {
        "friend": UserPublic(id=friend.id, name=friend.name, email=friend.email)
    }


@app.get("/v2/users/{user_id}/friends/id/{friend_id}")
async def get_friend_by_id_v2(
    user_id: int,
    friend_id: int,
    user_repo: UserRepository = Depends(get_user_repository),
    friends_repo: FriendshipRepository = Depends(get_friendship_repository),
):
    await validate_user_exists(user_id, user_repo)
    friend = await friends_repo.get_friend_by_id(user_id, friend_id)
    if not friend:
        raise HTTPException(status_code=404, detail="Friend not found.")
    return {
        "friend": UserPublic(id=friend.id, name=friend.name, email=friend.email)
    }


@app.delete("/v2/users/{user_id}/friends/name/{friend_name}", status_code=202)
async def delete_friendship_by_name_v2(
    user_id: int,
    friend_name: str,
    auth: AuthModel | None = None,
    user_repo: UserRepository = Depends(get_user_repository),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    friends_repo: FriendshipRepository = Depends(get_friendship_repository),
):
    if not await authenticate(auth, user_repo, auth_repo):
        raise HTTPException(status_code=401, detail="Unauthorized!")

    if auth.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not allowed.")

    await validate_user_exists(user_id, user_repo)

    friend_user = await user_repo.get_by_name(friend_name)
    if not friend_user:
        raise HTTPException(status_code=404, detail="Friend not found.")

    deleted = await friends_repo.delete_friendship(user_id, friend_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="No friendship found to delete.")
    return {"detail": f"Friendship with '{friend_name}' deleted."}


@app.delete("/v2/users/{user_id}/friends/id/{friend_id}", status_code=202)
async def delete_friendship_by_id_v2(
    user_id: int,
    friend_id: int,
    auth: AuthModel | None = None,
    user_repo: UserRepository = Depends(get_user_repository),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    friends_repo: FriendshipRepository = Depends(get_friendship_repository),
):
    if not await authenticate(auth, user_repo, auth_repo):
        raise HTTPException(status_code=401, detail="Unauthorized!")

    if auth.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not allowed.")

    await validate_user_exists(user_id, user_repo)
    await validate_user_exists(friend_id, user_repo)

    deleted = await friends_repo.delete_friendship(user_id, friend_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="No friendship found to delete.")
    return {"detail": f"Friendship with user {friend_id} deleted."}


# -------------- V1 --------------


@app.post("/users/", status_code=201)
async def create_user(
    user: UserSchema,
    response: Response,
    user_repo: UserRepository = Depends(get_user_repository),
):
    new_user = await user_repo.create(user.name, user.email, user.password)
    if new_user is None:
        response.status_code = 409
        return {"detail": "User or email already exists"}
    else:
        return {"user": UserSchema.from_db_model(new_user)}


@app.get("/users/")
async def list_users(user_repo: UserRepository = Depends(get_user_repository)):
    user_models = await user_repo.get_all()
    users = []
    for model in user_models:
        users.append(UserSchema.from_db_model(model))
    return {"users": users}


@app.get("/users/{name}")
async def get_user(name: str, user_repo: UserRepository = Depends(get_user_repository)):
    user = await user_repo.get_by_name(name)
    return {"user": user}


@app.post("/users/delete", status_code=202)
async def delete_user(
    user: UserSchema,
    response: Response,
    user_repo: UserRepository = Depends(get_user_repository),
):
    users = await user_repo.delete(user.name)
    if users.rowcount > 0:
        return {"detail": f"'{user.name}' deleted"}
    response.status_code = 404
    return {"detail": "No users to delete"}


@app.post("/users/{id}/avatar")
async def upload_avatar(
    id: int,
    file: UploadFile = File(...),
    user_repo: UserRepository = Depends(get_user_repository),
):
    validate_image_file(file)
    avatar_path = AVATAR_DIR / f"{id}.jpg"
    await save_avatar(file, avatar_path)
    return {"detail": "Avatar uploaded"}


@app.get("/users/{id}/avatar")
async def get_avatar(id: int):
    avatar_path = validate_avatar_exists(id)
    return FileResponse(avatar_path)


ui.run_with(app, mount_path="/admin", favicon="👤", title="User Admin")
