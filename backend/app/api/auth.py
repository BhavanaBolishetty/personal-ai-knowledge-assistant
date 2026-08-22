from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas import LoginRequest, SignupRequest, TokenResponse, UserResponse
from app.core.security import AuthError, create_access_token, hash_password, verify_password
from app.db import crud
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(request: SignupRequest, db: Session = Depends(get_db)):
    if crud.get_user_by_email(db, request.email) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = crud.create_user(db, email=request.email, hashed_password=hash_password(request.password))
    return _issue_token(user)


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, request.email)
    # Same generic message whether the email doesn't exist or the password
    # is wrong — confirming which one it was would let an attacker enumerate
    # registered emails.
    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    return _issue_token(user)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


def _issue_token(user: User) -> TokenResponse:
    try:
        token = create_access_token(user.id)
    except AuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return TokenResponse(token=token, user=UserResponse.model_validate(user))
