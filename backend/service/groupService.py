from fastapi import HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from repository.groupRepository import GroupRepository
from repository.userRepository import UserRepository  # Ci serve per recuperare l'utente da aggiungere!
from database import SessionLocal


# --- SCHEMAS ---
class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class GroupUserAdd(BaseModel):
    group_id: int
    user_id: int


# --- SERVICE ---
class GroupService:

    def list_groups(self):
        with SessionLocal() as db:
            return GroupRepository.get_all_groups(db)

    def create_group(self, group_in: GroupCreate):
        with SessionLocal() as db:
            return GroupRepository.create_group(
                db=db,
                name=group_in.name,
                description=group_in.description
            )

    def get_group(self, group_id: int):
        with SessionLocal() as db:
            group = GroupRepository.get_group_by_id(db, group_id)
            if not group:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Gruppo non trovato"
                )
            return group

    def update_group(self, group_id: int, group_update: GroupUpdate):
        with SessionLocal() as db:
            updated_group = GroupRepository.update_group(
                db=db,
                group_id=group_id,
                name=group_update.name,
                description=group_update.description
            )

            if not updated_group:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Gruppo non trovato"
                )
            return updated_group

    def delete_group(self, group_id: int):
        with SessionLocal() as db:
            success = GroupRepository.delete_group(db, group_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Gruppo non trovato"
                )
            return {"detail": f"Gruppo {group_id} eliminato con successo"}

    def add_user_to_group(self, payload: GroupUserAdd):
        with SessionLocal() as db:
            # 1. Recupera il gruppo
            group = GroupRepository.get_group_by_id(db, payload.group_id)
            if not group:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Gruppo non trovato"
                )

            # 2. Recupera l'utente
            # NOTA: Assumiamo che UserRepository abbia il metodo statico 'get_user_by_id'
            # (Adattalo se nel tuo userRepository usi l'approccio orientato agli oggetti visto prima)
            user = UserRepository.get_user_by_id(db, payload.user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Utente non trovato"
                )

            # 3. Effettua l'associazione
            return GroupRepository.add_user_to_group(db, group, user)

    def list_group_members(self, group_id: int):
        with SessionLocal() as db:
            group = GroupRepository.get_group_by_id(db, group_id)
            if not group:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Gruppo non trovato"
                )
            # SQLAlchemy ha già caricato (o caricherà lazy) gli utenti collegati
            return group.users

    def list_group_subjects(self, group_id: int):
        with SessionLocal() as db:
            group = GroupRepository.get_group_by_id(db, group_id)
            if not group:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Gruppo non trovato"
                )
            # Stessa cosa per le materie: sfruttiamo la back_populates definita nel modello
            return group.subjects


# Istanza esportata per l'uso nel Controller
group_service = GroupService()