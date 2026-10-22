"""
Script de migração: alunosv3.db (tabela flat) → alunosv3_novo.db (schema normalizado)
Execute uma única vez.  Pode ser executado várias vezes com segurança pois limpa as tabelas antes.
"""

import sqlite3
import os

ORIGEM = os.path.join(os.path.dirname(__file__), 'alunosv3.db')
DESTINO = os.path.join(os.path.dirname(__file__), 'alunosv3_novo.db')

orig = sqlite3.connect(ORIGEM)
orig.row_factory = sqlite3.Row
dest = sqlite3.connect(DESTINO)

orig_cur = orig.cursor()
dest_cur = dest.cursor()

# Limpa destino para re-execuções seguras
dest_cur.executescript("""
    DELETE FROM documento;
    DELETE FROM matricula;
    DELETE FROM saude;
    DELETE FROM endereco;
    DELETE FROM responsavel;
    DELETE FROM aluno;
    DELETE FROM sqlite_sequence WHERE name IN
        ('documento','matricula','saude','endereco','responsavel','aluno');
""")

orig_cur.execute("SELECT * FROM alunosImportados")
rows = orig_cur.fetchall()

migrados = 0
for r in rows:
    # 1. aluno
    dest_cur.execute("""
        INSERT INTO aluno (ra, rm, nome_completo, data_nascimento, sexo, raca_cor,
            nacionalidade, municipio_nascimento, rg_aluno, cpf_aluno,
            cartao_sus, certidao_nascimento, rne, gemeo)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        r['ra'], r['rm'], r['nome_completo'], r['data_nascimento'],
        r['sexo'], r['raca_cor'], r['nacionalidade'], r['municipio_nascimento'],
        r['rg_aluno'], r['cpf_aluno'],
        r['cartao_sus'], r['certidao_nascimento'],
        r['rne'], r['gemeo'],
    ))
    aluno_id = dest_cur.lastrowid

    # 2. responsavel
    dest_cur.execute("""
        INSERT INTO responsavel (aluno_id, nome_mae, cpf_mae, rg_mae, uf_rg_mae,
            expedicao_rg_mae, estado_civil_mae, profissao_mae, email_mae,
            nome_pai, cpf_pai, rg_pai, profissao_pai, responsavel_matricula,
            telefone1, telefone2, telefone3, telefone4,
            bolsa_familia, nis, pessoa1, pessoa2, pessoa3)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        aluno_id,
        r['nome_mae'], r['cpf_mae'], r['rg_mae'], r['uf_rg_mae'],
        r['expedicao_rg_mae'], r['estado_civil_mae'], r['profissao_mae'],
        r['email_mae'] if 'email_mae' in r.keys() else None,
        r['nome_pai'], r['cpf_pai'], r['rg_pai'], r['profissao_pai'],
        r['responsavel_matricula'],
        r['telefone1'], r['telefone2'], r['telefone3'], r['telefone4'],
        r['bolsa_familia'], r['nis'],
        r['pessoa1'], r['pessoa2'], r['pessoa3'],
    ))

    # 3. endereco  (campo legado 'cidade' vai para cidade, 'cidade_endereco' tbm)
    cidade_end = r['cidade_endereco'] if r['cidade_endereco'] else r['cidade']
    dest_cur.execute("""
        INSERT INTO endereco (aluno_id, logradouro, numero, bairro, cidade, estado, cep)
        VALUES (?,?,?,?,?,?,?)
    """, (
        aluno_id,
        r['logradouro'], r['numero'], r['bairro'],
        cidade_end, r['estado'], r['cep'],
    ))

    # 4. saude
    dest_cur.execute("""
        INSERT INTO saude (aluno_id, tipo_sanguineo, alergico, diabetico,
            lactose, aplv, plano, uniforme, calcado, observacoes)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        aluno_id,
        r['tipo_sanguineo'], r['alergico'], r['diabetico'],
        r['lactose'], r['aplv'], r['plano'],
        r['uniforme'], r['calcado'], r['observacoes'],
    ))

    # 5. matricula
    try:
        contrib = float(r['contribuicao']) if r['contribuicao'] else None
    except (ValueError, TypeError):
        contrib = None

    dest_cur.execute("""
        INSERT INTO matricula (aluno_id, nivel, sala, integral, ano, escola_anterior,
            contribuicao)
        VALUES (?,?,?,?,?,?,?)
    """, (
        aluno_id,
        r['nivel'], 'Sem Sala', r['integral'], r['ano'],
        r['escola_anterior'], contrib,
    ))

    migrados += 1

dest.commit()
orig.close()
dest.close()

print(f"✅  Migração concluída: {migrados} aluno(s) transferido(s).")
