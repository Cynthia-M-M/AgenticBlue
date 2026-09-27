from fastapi import FastAPI
from demo_project.backend.schemas import AppointmentCreate

app = FastAPI(title="Demo Appointments API")


@app.post("/appointments")
def create_appointment(appointment: AppointmentCreate):
    return {
        "message": "Appointment created",
        "patient_id": appointment.patient_id,
        "doctor_id": appointment.doctor_id,
    }
