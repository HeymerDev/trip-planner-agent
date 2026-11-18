// Autenticacion con Amazon Cognito (flujo SRP; sin secretos en el navegador).
import {
  AuthenticationDetails,
  CognitoUser,
  CognitoUserAttribute,
  CognitoUserPool,
} from 'amazon-cognito-identity-js'
import { config } from './config'

const pool = new CognitoUserPool({ UserPoolId: config.userPoolId, ClientId: config.clientId })

const friendly = (err) => {
  switch (err?.code || err?.name) {
    case 'UsernameExistsException':
      return 'Ya existe una cuenta con ese correo.'
    case 'InvalidPasswordException':
      return 'La contraseña debe tener 8+ caracteres, mayúscula, minúscula y número.'
    case 'NotAuthorizedException':
    case 'UserNotFoundException':
      return 'Correo o contraseña incorrectos.'
    case 'InvalidParameterException':
      return 'Revisa el correo y la contraseña.'
    case 'TooManyRequestsException':
    case 'LimitExceededException':
      return 'Demasiados intentos. Espera un momento.'
    default:
      return 'No se pudo completar la operación. Intenta de nuevo.'
  }
}

export function signUp(email, password) {
  return new Promise((resolve, reject) => {
    pool.signUp(email, password, [new CognitoUserAttribute({ Name: 'email', Value: email })], [], (err) =>
      err ? reject(new Error(friendly(err))) : resolve(),
    )
  })
}

export function signIn(email, password) {
  const user = new CognitoUser({ Username: email, Pool: pool })
  const details = new AuthenticationDetails({ Username: email, Password: password })
  return new Promise((resolve, reject) => {
    user.authenticateUser(details, {
      onSuccess: (session) => resolve(session),
      onFailure: (err) => reject(new Error(friendly(err))),
    })
  })
}

export function signOut() {
  pool.getCurrentUser()?.signOut()
}

/** Sesion vigente (refresca el token si hace falta) o null. */
export function getSession() {
  return new Promise((resolve) => {
    const user = pool.getCurrentUser()
    if (!user) return resolve(null)
    user.getSession((err, session) => resolve(!err && session?.isValid() ? session : null))
  })
}

/** Access token para API Gateway y AgentCore (JWT de Cognito). */
export async function getAccessToken() {
  const session = await getSession()
  return session ? session.getAccessToken().getJwtToken() : null
}

/** Datos del usuario desde el ID token (correo y sub). */
export function userFromSession(session) {
  const payload = session.getIdToken().payload
  return { sub: payload.sub, email: payload.email }
}
