from fastapi import HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
from repository.userRepository import UserRepository
# Assicurati di importare il costruttore della sessione dal tuo file database
from database import SessionLocal


# --- SCHEMAS ---
class UserUpdate(BaseModel):
    """Schema Pydantic per validare i dati di aggiornamento"""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None  # In uno scenario reale, andrà hashata


# --- SERVICE ---
class UserService:

    def get_profile(self, user_id: int):
        with SessionLocal() as db:
            repo = UserRepository(db)
            user = repo.get_user_by_id(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Utente non trovato"
                )
            return user

    def update_profile(self, user_id: int, user_data: UserUpdate):
        with SessionLocal() as db:
            repo = UserRepository(db)
            db_user = repo.get_user_by_id(user_id)

            if not db_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Utente non trovato"
                )

            # Converte il modello Pydantic in un dizionario, escludendo i campi non inviati
            update_dict = user_data.model_dump(exclude_unset=True)

            # Gestione eventuale dell'hashing della password prima del salvataggio
            if "password" in update_dict:
                # update_dict["password_hash"] = hash_function(update_dict.pop("password"))
                update_dict["password_hash"] = update_dict.pop("password")  # Placeholder

            if not update_dict:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nessun dato valido fornito per l'aggiornamento"
                )

            updated_user = repo.update_user(db_user, update_dict)
            return updated_user

    def list_user_groups(self, user_id: int):
        with SessionLocal() as db:
            repo = UserRepository(db)
            self._verify_user_exists(repo, user_id)
            return repo.get_user_groups(user_id)

    def list_user_subjects(self, user_id: int):
        with SessionLocal() as db:
            repo = UserRepository(db)
            self._verify_user_exists(repo, user_id)
            return repo.get_user_subjects(user_id)

    # --- METODI HELPER PRIVATI ---
    def _verify_user_exists(self, repo: UserRepository, user_id: int):
        """Metodo di supporto per evitare duplicazioni di codice"""
        if not repo.get_user_by_id(user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utente non trovato"
            )


# Istanza singleton esportata per l'uso nel controller
user_service = UserService()