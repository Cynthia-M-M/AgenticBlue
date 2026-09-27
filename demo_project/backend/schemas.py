from pydantic import BaseModel


class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
