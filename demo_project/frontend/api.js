// Demo frontend API client
// BUG: sends "doctor_id" (camelCase) but backend expects "doctor_id" (snake_case)

async function createAppointment(patientId, doctor_id) {
    const response = await fetch("/appointments", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            patient_id: patientId,
            doctor_id: doctor_id      // <-- intentional drift: should be doctor_id
        })
    });

    return response.json();
}
