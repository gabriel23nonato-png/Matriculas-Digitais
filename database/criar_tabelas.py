import sqlite3

conn = sqlite3.connect("database\\alunosv3.db")
cursor = conn.cursor()

novos_campos = [
    "doc_cpf_aluno",
    "cartao_sus",
    "certidao_nascimento",
    "municipio_nascimento",
    "distrito",
    "expedicao_rg_aluno",
    "nacionalidade",
    "sexo",
    "raca_cor",
    "tipo_sanguineo",
    "alergico",
    "diabetico",
    "observacoes",
    "nome_mae",
    "profissao_mae",
    "email_mae",
    "cpf_mae",
    "rg_mae",
    "uf_rg_mae",
    "expedicao_rg_mae",
    "estado_civil_mae",
    "nome_pai",
    "profissao_pai",
    "telefone1",
    "telefone2",
    "telefone3",
    "telefone4",
    "bolsa_familia",
    "nis",
    "plano",
    "escola_anterior",
    "ano",
    "cidade",
    "estado",
    "logradouro",
    "numero",
    "bairro",
    "cidade_endereco",
    "cep",
    "nivel",
]

for campo in novos_campos:
    try:
        cursor.execute(f"ALTER TABLE alunosImportados ADD COLUMN {campo} TEXT")
    except sqlite3.OperationalError:
        pass  # coluna já existe

conn.commit()
conn.close()
