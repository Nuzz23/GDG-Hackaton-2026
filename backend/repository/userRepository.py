from sqlalchemy.orm import Session
from model.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_id(self, user_id: int) -> User | None:
        """Recupera un utente dal DB tramite ID."""
        return self.db.query(User).filter(User.id == user_id).first()

    def update_user(self, db_user: User, update_data: dict) -> User:
        """Aggiorna i campi di un utente esistente."""
        for key, value in update_data.items():
            setattr(db_user, key, value)

        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def get_user_groups(self, user_id: int) -> list:
        """
        Recupera i gruppi dell'utente.
        Da implementare con il modello Group (es. Many-to-Many).
        """
        # Esempio: return self.db.query(Group).join(user_groups).filter(user_groups.c.user_id == user_id).all()
        return [{"id": 1, "name": "Admin Group"}]  # Mock data

    def get_user_subjects(self, user_id: int) -> list:
        """
        Recupera le materie/soggetti dell'utente.
        Da implementare con il modello Subject (es. One-to-Many o Many-to-Many).
        """
        # Esempio: return self.db.query(Subject).filter(Subject.user_id == user_id).all()
        return [{"id": 101, "name": "Mathematics"}]  # Mock data