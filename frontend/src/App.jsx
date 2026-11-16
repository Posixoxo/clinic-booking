import { useState, useEffect } from "react";
import { format } from "date-fns";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL;
const API_KEY = import.meta.env.VITE_API_KEY;

function App() {
  const [slots, setSlots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [bookingResult, setBookingResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Fetch available slots
  const fetchSlots = async () => {
    try {
      setLoading(true);
      setError("");
      const res = await fetch(`${API_BASE}/slots`, {
        headers: {
          "X-API-Key": API_KEY,
        },
      });

      if (!res.ok) {
        throw new Error("Failed to load slots");
      }

      const data = await res.json();
      // Only show available slots
      setSlots(data.filter((s) => s.available));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSlots();
  }, []);

  const handleBook = async (e) => {
    e.preventDefault();
    if (!selectedSlot || !name.trim() || !email.trim()) return;

    setSubmitting(true);
    setError("");
    setBookingResult(null);

    try {
      const res = await fetch(`${API_BASE}/bookings`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": API_KEY,
        },
        body: JSON.stringify({
          slot_id: selectedSlot.id,
          name: name.trim(),
          email: email.trim(),
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail?.error || data.error || "Booking failed");
      }

      setBookingResult(data);
      setSelectedSlot(null);
      setName("");
      setEmail("");
      // Refresh slots so the booked one disappears
      fetchSlots();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container">
      <header>
        <h1>Clinic Booking</h1>
        <p>Select an available slot and book your appointment</p>
      </header>

      {error && <div className="error">{error}</div>}

      {bookingResult && (
        <div className="success">
          <h3>Booking Confirmed!</h3>
          <p>
            <strong>Booking ID:</strong> {bookingResult.id}
          </p>
          <p>
            <strong>Name:</strong> {bookingResult.name}
          </p>
          <p>
            <strong>Email:</strong> {bookingResult.email}
          </p>
          <p>
            <strong>Status:</strong> {bookingResult.status}
          </p>
          <button onClick={() => setBookingResult(null)}>Book another</button>
        </div>
      )}

      {!bookingResult && (
        <>
          <section className="slots-section">
            <h2>Available Slots</h2>

            {loading ? (
              <p>Loading slots...</p>
            ) : slots.length === 0 ? (
              <p>No available slots at the moment.</p>
            ) : (
              <div className="slots-grid">
                {slots.map((slot) => (
                  <div
                    key={slot.id}
                    className={`slot-card ${
                      selectedSlot?.id === slot.id ? "selected" : ""
                    }`}
                    onClick={() => setSelectedSlot(slot)}
                  >
                    <div className="provider">{slot.provider}</div>
                    <div className="time">
                      {format(new Date(slot.start), "EEE, MMM d")}
                    </div>
                    <div className="time">
                      {format(new Date(slot.start), "h:mm a")} –{" "}
                      {format(new Date(slot.end), "h:mm a")}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {selectedSlot && (
            <section className="booking-form">
              <h2>Book this slot</h2>
              <p className="selected-info">
                {selectedSlot.provider} •{" "}
                {format(new Date(selectedSlot.start), "EEE, MMM d • h:mm a")}
              </p>

              <form onSubmit={handleBook}>
                <div className="form-group">
                  <label>Full Name</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Ada Obi"
                    required
                  />
                </div>

                <div className="form-group">
                  <label>Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="ada@example.com"
                    required
                  />
                </div>

                <button type="submit" disabled={submitting}>
                  {submitting ? "Booking..." : "Confirm Booking"}
                </button>
              </form>
            </section>
          )}
        </>
      )}
    </div>
  );
}

export default App;