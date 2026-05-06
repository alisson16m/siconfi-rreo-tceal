# Skill: /validar-api

Valida a integridade da integração com a API do SICONFI executando uma
sequência de verificações automatizadas.

## Instruções

Execute as etapas abaixo **na ordem indicada**. Relate o resultado de cada
etapa antes de avançar para a próxima. Se qualquer etapa falhar, interrompa
e informe o erro detalhadamente.

### Etapa 1 — Testes unitários

Execute a suíte de testes completa:

```bash
.venv\Scripts\python.exe -m pytest tests/ --tb=short -q
```

Critério de sucesso: todos os testes passam sem erros ou falhas.

### Etapa 2 — Consistência da fixture de referência

Verifique se o arquivo `tests/fixtures/arapiraca_2025.json` existe e está
bem formado:

```bash
.venv\Scripts\python.exe -c "
import json, pathlib, sys
path = pathlib.Path('tests/fixtures/arapiraca_2025.json')
if not path.exists():
    print('ERRO: fixture não encontrada')
    sys.exit(1)
data = json.loads(path.read_text(encoding='utf-8'))
itens = data.get('items', data) if isinstance(data, dict) else data
print(f'OK — {len(itens)} itens na fixture')
"
```

Critério de sucesso: arquivo existe, é JSON válido e contém itens.

### Etapa 3 — Consistência da lista de entes

Verifique se todos os entes de Alagoas estão cadastrados corretamente:

```bash
.venv\Scripts\python.exe -c "
from src.municipios_al import ENTES_AL
municipios = [e for e in ENTES_AL if e.esfera == 'M']
estados = [e for e in ENTES_AL if e.esfera == 'E']
print(f'Municípios: {len(municipios)}')
print(f'Estados: {len(estados)}')
ids_duplicados = [e.id_ente for e in ENTES_AL]
duplicatas = [x for x in ids_duplicados if ids_duplicados.count(x) > 1]
if duplicatas:
    print(f'ALERTA: id_ente duplicados: {set(duplicatas)}')
else:
    print('OK — sem id_ente duplicados')
assert len(estados) == 1, 'Deveria haver exatamente 1 ente estadual'
assert len(municipios) == 102, f'Esperado 102 municípios, encontrado {len(municipios)}'
print('Validação concluída com sucesso.')
"
```

Critério de sucesso: 1 ente estadual, 102 municípios, sem `id_ente` duplicados.

### Etapa 4 — Conectividade com a API do SICONFI (Arapiraca/2024)

Faça uma consulta real à API do SICONFI usando o município de Arapiraca
e o exercício 2024 como caso de teste:

```bash
.venv\Scripts\python.exe -c "
from src.municipios_al import ENTES_AL
from src.siconfi_client import fetch_rreo_anexo1, SiconfiEmptyResponseError, SiconfiNetworkError, SiconfiInvalidJsonError

arapiraca = next((e for e in ENTES_AL if 'Arapiraca' in e.nome), None)
if not arapiraca:
    print('ERRO: Arapiraca não encontrada em ENTES_AL')
    raise SystemExit(1)

print(f'Consultando: {arapiraca.nome} (id_ente={arapiraca.id_ente}), exercício 2024...')
try:
    response = fetch_rreo_anexo1(
        id_ente=arapiraca.id_ente,
        exercicio=2024,
        esfera=arapiraca.esfera,
    )
    print(f'OK — {len(response.items)} itens retornados pela API')
except SiconfiEmptyResponseError:
    print('AVISO: API retornou resposta vazia (dados podem não estar disponíveis para 2024)')
except SiconfiNetworkError as e:
    print(f'ERRO de rede: {e}')
    raise SystemExit(1)
except SiconfiInvalidJsonError as e:
    print(f'ERRO de JSON: {e}')
    raise SystemExit(1)
"
```

Critério de sucesso: API responde sem erro de rede ou JSON inválido.
Resposta vazia (dados não disponíveis) é considerada aviso, não falha.

### Etapa 5 — Relatório final

Ao final, exiba um resumo consolidado no formato:

```
=== Relatório de Validação da API SICONFI ===
Etapa 1 — Testes unitários:         [PASSOU / FALHOU]
Etapa 2 — Fixture de referência:    [PASSOU / FALHOU / AVISO: <detalhe>]
Etapa 3 — Lista de entes:           [PASSOU / FALHOU]
Etapa 4 — Conectividade com a API:  [PASSOU / AVISO / FALHOU]
=============================================
Status geral: [OK / ATENÇÃO / FALHA CRÍTICA]
```
