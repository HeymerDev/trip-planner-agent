"""
Trigger PreSignUp de Cognito: auto-confirma el registro y marca el correo como verificado.

Decision de la demostracion (ver docs/sdd/design.md, seccion 10): evita depender del envio de
correos de verificacion. En produccion se quitaria este trigger para exigir verificacion real.
"""


def handler(event, context):
    event["response"]["autoConfirmUser"] = True
    if "email" in event["request"].get("userAttributes", {}):
        event["response"]["autoVerifyEmail"] = True
    return event
