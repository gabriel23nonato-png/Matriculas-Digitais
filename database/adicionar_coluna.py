import sqlite3

# Conectar ao banco de dados (cria se não existir)
conn = sqlite3.connect("database\\database\\alunosv3.db")
cursor = conn.cursor()

# Comando SQL para adicionar a nova coluna
# Exemplo: Adicionar 'email' do tipo TEXT na tabela 'alunos_v3'
cursor.execute("SELECT * FROM alunosImportados LIMIT 0")
# cursor.execute("ALTER TABLE alunosImportados ADD COLUMN rne TEXT")
# cursor.execute("ALTER TABLE alunosImportados ADD COLUMN integral TEXT")
# cursor.execute("ALTER TABLE alunosImportados ADD COLUMN uniforme TEXT")
# cursor.execute("ALTER TABLE alunosImportados ADD COLUMN gemeo TEXT")
# cursor.execute("ALTER TABLE alunosImportados ADD COLUMN cpf_pai TEXT")
# cursor.execute("ALTER TABLE alunosImportados ADD COLUMN rg_pai TEXT")
# cursor.execute("ALTER TABLE alunosImportados ADD COLUMN pessoa1 TEXT")
# cursor.execute("ALTER TABLE alunosImportados ADD COLUMN contribuicao TEXT")
# cursor.execute("ALTER TABLE alunosImportados ADD COLUMN pessoa3 TEXT")
# cursor.execute("ALTER TABLE alunosImportados ADD COLUMN pessoa2 TEXT")
# cursor.execute("ALTER TABLE alunosImportados ADD COLUMN calcado TEXT")
# cursor.execute("ALTER TABLE alunosImportados ADD COLUMN aplv TEXT")

# Salvar as alterações
conn.commit()

# Fechar conexão
conn.close()
print("Coluna adicionada com sucesso!")

# Salvar as alterações
conn.commit()

# Fechar conexão
conn.close()
print("Coluna adicionada com sucesso!")
