from fastapi import Header, HTTPException, Depends
from app.database import supabase

async def verificar_perfil(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de autenticação ausente ou inválido")
    
    token = authorization.split(" ")[1]
    
    try:
        # Valida o token diretamente com o Supabase Auth
        user_response = supabase.auth.get_user(token)
        user_id = user_response.user.id
        
        # Busca a role (papel) do usuário na tabela que criamos
        usuario_db = supabase.table("usuarios").select("role", "ativo").eq("id", user_id).single().execute()
        
        if not usuario_db.data or not usuario_db.data.get("ativo"):
            raise HTTPException(status_code=403, detail="Usuário inativo ou não encontrado")
            
        return {"id": user_id, "role": usuario_db.data["role"]}
        
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Falha na autenticação: {str(e)}")