from fastapi import HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
# Importa il tuo nuovo repository e il costruttore della sessione
from repository.subjectRepository import SubjectRepository
from database import SessionLocal


# --- SCHEMAS ---
class SubjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    deadline: Optional[datetime] = None


class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    deadline: Optional[datetime] = None


# --- SERVICE ---
class SubjectService:

    def list_subjects(self, group_id: int):
        with SessionLocal() as db:
            # Usa il metodo statico passando il db
            return SubjectRepository.get_subjects_by_group(db, group_id=group_id)

    def create_subject(self, group_id: int, subject_in: SubjectCreate):
        with SessionLocal() as db:
            # Espandiamo i dati del Pydantic model come parametri espliciti
            return SubjectRepository.create_subject(
                db=db,
                name=subject_in.name,
                group_id=group_id,
                description=subject_in.description,
                deadline=subject_in.deadline
            )

    def get_subject(self, group_id: int, subject_id: int):
        with SessionLocal() as db:
            subject = SubjectRepository.get_subject_by_id(db, group_id, subject_id)

            # Controllo di sicurezza: verifica che la materia esista E appartenga al gruppo
            if not subject or subject.group_id != group_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Materia non trovata o non appartenente a questo gruppo"
                )
            return subject

    def update_subject(self, group_id: int, subject_id: int, subject_update: SubjectUpdate):
        with SessionLocal() as db:
            # 1. Verifichiamo che l'utente abbia il diritto di modificare questa materia (tramite group_id)
            subject = SubjectRepository.get_subject_by_id(db, group_id, subject_id)
            if not subject or subject.group_id != group_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Materia non trovata o non appartenente a questo gruppo"
                )

            # 2. Procediamo con l'aggiornamento
            updated_subject = SubjectRepository.update_subject(
                db=db,
                subject_id=subject_id,
                name=subject_update.name,
                description=subject_update.description,
                deadline=subject_update.deadline
            )
            return updated_subject

    def delete_subject(self, group_id: int, subject_id: int):
        with SessionLocal() as db:
            # 1. Verifica appartenenza al gruppo
            subject = SubjectRepository.get_subject_by_id(db, group_id, subject_id)
            if not subject or subject.group_id != group_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Materia non trovata o non appartenente a questo gruppo"
                )

            # 2. Procediamo con l'eliminazione
            success = SubjectRepository.delete_subject(db, group_id, subject_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Errore durante l'eliminazione della materia"
                )

            return {"detail": f"Materia {subject_id} eliminata con successo"}


# Istanza esportata per l'uso nel Controller
subject_service = SubjectService()