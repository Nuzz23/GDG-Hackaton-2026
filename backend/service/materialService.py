import os
import shutil
from fastapi import HTTPException, status, UploadFile
from pydantic import BaseModel
from typing import Optional
from repository.materialRepository import MaterialRepository
from repository.subjectRepository import SubjectRepository
from database import SessionLocal


# --- SCHEMAS ---
# MaterialCreate non serve più per l'upload (usiamo Form), ma teniamo l'Update
class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    file_size: Optional[int] = None


# --- SERVICE ---
class MaterialService:

    def upload_material(self, group_id: int, file: UploadFile, name: str, subject_id: int):
        with SessionLocal() as db:
            # 1. Verifica di sicurezza: il subject appartiene al gruppo?
            subject = SubjectRepository.get_subject_by_id(
                db=db,
                group_id=group_id,
                subject_id=subject_id
            )

            if not subject:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Materia non trovata o non appartenente a questo gruppo."
                )

            # 2. Configura il percorso di salvataggio fisico
            # Esempio: salva in "uploads/group_1/subject_5/nomefile.pdf"
            upload_dir = os.path.join("uploads", f"group_{group_id}", f"subject_{subject_id}")
            os.makedirs(upload_dir, exist_ok=True)

            # Assicuriamoci che il nome del file sia sicuro (in prod usa librerie come werkzeug.utils.secure_filename)
            safe_filename = file.filename.replace(" ", "_")
            file_path = os.path.join(upload_dir, safe_filename)

            # 3. Salva il file su disco
            try:
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Errore durante il salvataggio del file: {str(e)}"
                )
            finally:
                file.file.close()

            # 4. Calcola la dimensione del file salvato (in bytes)
            file_size = os.path.getsize(file_path)

            # 5. Salva i metadati nel database
            return MaterialRepository.upload_material(
                db=db,
                name=name,
                path=file_path,
                subject_id=subject_id,
                file_size=file_size
            )

    def get_material(self, group_id: int, material_id: int):
        with SessionLocal() as db:
            material = MaterialRepository.get_material_by_id(db, group_id, material_id)

            if not material:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Materiale non trovato o non accessibile per questo gruppo"
                )
            return material

    def list_materials_by_subject(self, group_id: int, subject_id: int):
        """List all materials of a subject (verified to belong to the group)."""
        with SessionLocal() as db:
            subject = SubjectRepository.get_subject_by_id(
                db=db, group_id=group_id, subject_id=subject_id
            )
            if not subject:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Materia non trovata o non appartenente a questo gruppo.",
                )
            return MaterialRepository.get_materials_by_subject(db, group_id, subject_id)

    def update_material(self, group_id: int, material_id: int, material_update: MaterialUpdate):
        with SessionLocal() as db:
            updated_material = MaterialRepository.update_material(
                db=db,
                group_id=group_id,
                material_id=material_id,
                name=material_update.name,
                path=material_update.path,
                file_size=material_update.file_size
            )

            if not updated_material:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Materiale non trovato o non accessibile per questo gruppo"
                )
            return updated_material

    def delete_material(self, group_id: int, material_id: int):
        with SessionLocal() as db:
            success = MaterialRepository.delete_material(db, group_id, material_id)

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Materiale non trovato o non accessibile per questo gruppo"
                )

            return {"detail": f"Materiale {material_id} eliminato con successo"}


# Istanza esportata per l'uso nel Controller
material_service = MaterialService()