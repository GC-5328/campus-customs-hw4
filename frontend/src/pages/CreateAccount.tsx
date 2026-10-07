import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { signup, type SignupData } from '../auth'

const MIN_PASSWORD_LENGTH = 8

const EMPTY_FORM: SignupData = {
  first_name: '',
  last_name: '',
  email: '',
  password: '',
  confirm_password: '',
}

export default function CreateAccount() {
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState<SignupData>(EMPTY_FORM)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (user) return <Navigate to="/" replace />

  const passwordsMismatch = form.confirm_password !== '' && form.password !== form.confirm_password

  function update(event: ChangeEvent<HTMLInputElement>) {
    setForm({ ...form, [event.target.name]: event.target.value })
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (form.password !== form.confirm_password) {
      setError("Passwords don't match.")
      return
    }
    setSubmitting(true)
    try {
      setUser(await signup(form))
      navigate('/')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="auth-card">
      <h1>Create account</h1>
      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <label>
            First name
            <input name="first_name" autoComplete="given-name" value={form.first_name} onChange={update} required />
          </label>
          <label>
            Last name
            <input name="last_name" autoComplete="family-name" value={form.last_name} onChange={update} required />
          </label>
        </div>
        <label>
          Email
          <input type="email" name="email" autoComplete="email" value={form.email} onChange={update} required />
        </label>
        <label>
          Password
          <input
            type="password"
            name="password"
            autoComplete="new-password"
            minLength={MIN_PASSWORD_LENGTH}
            value={form.password}
            onChange={update}
            required
          />
          <span className="hint">At least {MIN_PASSWORD_LENGTH} characters.</span>
        </label>
        <label>
          Re-enter password
          <input
            type="password"
            name="confirm_password"
            autoComplete="new-password"
            value={form.confirm_password}
            onChange={update}
            aria-invalid={passwordsMismatch}
            required
          />
          {passwordsMismatch && <span className="hint error">Passwords don't match.</span>}
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" className="button" disabled={submitting || passwordsMismatch}>
          {submitting ? 'Creating account…' : 'Create account'}
        </button>
      </form>
      <p className="muted">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </section>
  )
}
