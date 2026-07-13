from fastapi import Header, HTTPException, status

from app.database import supabase


async def verificar_perfil(authorization: str | None = Header(default=None)) -> dict:
    """Valida o JWT e devolve apenas o perfil ativo do usuário."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação ausente ou inválido.",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token de autenticação ausente ou inválido.")

    try:
        user_response = supabase.auth.get_user(token)
        user_id = user_response.user.id
        usuario_db = (
            supabase.table("usuarios")
            .select("id, nome, role, ativo")
            .eq("id", user_id)
            .single()
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Token de autenticação inválido ou expirado.") from exc

    perfil = usuario_db.data
    if not perfil or not perfil.get("ativo"):
        raise HTTPException(status_code=403, detail="Usuário inativo ou sem perfil de acesso.")

    return {"id": user_id, "nome": perfil["nome"], "role": perfil["role"]}
