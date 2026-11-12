# Projeto: Point Perucaba Stories — Automação de Instagram

## 1. Papel e responsabilidade

Atue como Engenheiro de Software Sênior, com experiência em Python, APIs REST, Meta Graph API, GitHub Actions, CI/CD, segurança de aplicações e automações em nuvem.

Você será responsável por projetar e implementar uma solução de automação de publicações de Instagram Stories para o estabelecimento Point Perucaba.

Não quero apenas um script isolado. Quero um pequeno sistema de software, organizado, documentado, testável, seguro e preparado para execução contínua.

Trabalhe com autonomia técnica, mas explique as decisões importantes. Não invente funcionalidades da API nem presuma que uma integração está funcionando sem testá-la.

## 2. Objetivo do projeto

Desenvolver uma automação que publique diariamente um Instagram Story, utilizando uma imagem específica para cada dia da semana.

O calendário será fixo e recorrente:

| Dia | Conteúdo |
|---|---|
| Segunda-feira | Arte 01 |
| Terça-feira | Arte 02 |
| Quarta-feira | Arte 03 |
| Quinta-feira | Arte 04 |
| Sexta-feira | Arte 05 |
| Sábado | Arte 06 |
| Domingo | Arte 07 |

A automação deverá repetir esse calendário indefinidamente, sem necessidade de agendamento manual semanal.

### Requisitos funcionais

1. Executar automaticamente todos os dias às 08h00.
2. Utilizar o fuso horário `America/Sao_Paulo`.
3. Identificar corretamente o dia da semana.
4. Selecionar a imagem correspondente ao dia.
5. Publicar a imagem como Instagram Story.
6. Registrar o resultado da publicação.
7. Evitar publicações duplicadas na mesma data.
8. Informar erros de autenticação, indisponibilidade ou falha de publicação.
9. Permitir substituição das imagens sem alterar a lógica do sistema.
10. Permitir execução manual para testes.

## 3. Restrições financeiras e infraestrutura

O orçamento disponível é R$ 0,00.

Não utilize:
- VPS paga.
- Servidores contratados.
- n8n Cloud.
- Serviços pagos de automação.
- APIs comerciais pagas.
- Hospedagem que exija cartão ou assinatura.

A infraestrutura principal deverá utilizar:

- GitHub.
- GitHub Actions.
- Python.
- Instagram Graph API oficial da Meta.
- GitHub Secrets para armazenamento de credenciais.

Utilize os recursos gratuitos disponíveis, respeitando os limites de uso e os termos de cada plataforma.

O computador do proprietário não poderá ser uma dependência. A automação deve continuar funcionando mesmo quando ele estiver desligado.

Pesquise a documentação atual do GitHub Actions e confirme as cotas gratuitas aplicáveis ao tipo de repositório escolhido.

## 4. Arquitetura técnica

Utilize Python como linguagem principal.

O GitHub Actions será responsável pela execução programada.

O sistema deverá ter uma separação lógica entre:

- Agendamento.
- Identificação do dia da semana.
- Seleção da imagem.
- Validação do arquivo.
- Autenticação na Meta.
- Criação do container de mídia.
- Publicação do Story.
- Registro de execução.
- Tratamento de erros.

### Agendamento

Criar um workflow em `.github/workflows/daily-story.yml`.

O workflow deverá executar diariamente às 08h00 de Brasília.

O GitHub Actions utiliza UTC no agendamento cron. Portanto, considere inicialmente `11:00 UTC`, equivalente a 08h00 em `America/Sao_Paulo`.

Documente essa conversão e a ausência de garantia de execução exatamente no minuto programado.

Adicione também a possibilidade de execução manual por `workflow_dispatch`.

A execução manual deverá oferecer opção de simulação, sem publicar conteúdo real.

## 5. Integração com Instagram Graph API

Utilize exclusivamente a API oficial da Meta.

Antes de implementar, consulte a documentação oficial atualizada:

https://developers.facebook.com/docs/instagram-platform/

Pesquise especificamente:
- Instagram Content Publishing API.
- Publicação de Instagram Stories.
- Autenticação via Facebook Login.
- Permissões necessárias.
- Obtenção do Instagram Business Account ID.
- Obtenção do Page ID.
- Access Tokens.
- Long-Lived Access Tokens.
- Renovação e expiração de tokens.
- Limitações de publicação.

A conta Instagram já é Business, mas ainda será necessário vinculá-la a uma Página do Facebook.

A integração deve contemplar a criação e publicação de mídia utilizando os endpoints oficiais da versão vigente da Graph API.

Para imagens, investigue e implemente o fluxo oficial de criação de container com `media_type=STORIES` e publicação com `media_publish`, validando os parâmetros na documentação atual.

Não invente endpoints, permissões ou parâmetros.

Utilize uma versão explícita e suportada da Graph API, configurável por variável de ambiente.

### Segurança da autenticação

As credenciais não poderão estar no código-fonte.

Utilize GitHub Secrets para:

- `META_ACCESS_TOKEN`
- `META_IG_USER_ID`

Inclua outras variáveis somente se forem tecnicamente necessárias.

Nunca registre tokens completos nos logs.

Implemente tratamento para tokens expirados, inválidos e permissões insuficientes.

Documente o procedimento de renovação do token. Não prometa renovação automática se a Meta não oferecer suporte para o fluxo de autenticação utilizado.

## 6. Armazenamento das imagens

O sistema deverá trabalhar com sete imagens, uma para cada dia.

Sugestão de organização:

`assets/stories/`

Arquivos:

- segunda.jpg
- terca.jpg
- quarta.jpg
- quinta.jpg
- sexta.jpg
- sabado.jpg
- domingo.jpg

A Meta precisa conseguir acessar as imagens por URLs públicas.

Investigue a melhor alternativa gratuita para hospedamento dessas imagens.

Considere GitHub Pages como primeira alternativa, verificando se os arquivos podem ser acessados diretamente pelos servidores da Meta.

Não presuma que uma URL do repositório GitHub será automaticamente compatível com a API.

Implemente uma verificação HTTP para garantir que:
- A URL responde corretamente.
- O arquivo está publicamente acessível.
- O Content-Type é compatível com imagem.
- O formato é aceito pela Meta.
- O arquivo não está vazio.

Se GitHub Pages não for adequado, apresente outra alternativa gratuita antes de implementar uma dependência externa.

As imagens serão substituídas pelo proprietário quando necessário.

## 7. Seleção automática das imagens

Implemente uma função responsável por identificar o dia da semana.

Utilize `zoneinfo` com o fuso `America/Sao_Paulo`.

Exemplo conceitual:

Segunda-feira → segunda.jpg.

Terça-feira → terca.jpg.

E assim sucessivamente.

A função deverá ser independente da rotina de publicação, facilitando testes unitários.

Não utilize o fuso horário UTC para decidir qual imagem publicar.

## 8. Controle de duplicidade

Esse requisito é importante.

O GitHub Actions pode atrasar ou repetir execuções.

Implemente um mecanismo persistente para identificar se já houve uma publicação bem-sucedida naquela data.

Considere armazenar um registro por data, com:
- Data da publicação.
- Dia da semana.
- Nome da imagem.
- ID do container.
- ID da mídia publicada, quando disponível.
- Horário da execução.
- Resultado.

O mecanismo deverá impedir uma segunda publicação automática na mesma data.

Considere concorrência entre execuções e possíveis falhas durante a atualização do registro.

Não trate apenas um arquivo temporário do processo como mecanismo de persistência.

Explique as limitações de consistência caso a publicação seja concluída na Meta, mas o registro local falhe ao ser salvo.

## 9. Logs e monitoramento

Cada execução deverá registrar:

- Data e horário.
- Dia identificado.
- Imagem selecionada.
- Etapa executada.
- Resultado da autenticação.
- Resultado da publicação.
- Mensagem de erro, quando houver.

Não exponha dados sensíveis.

Implemente logs claros e úteis para diagnóstico.

Não é necessário criar um painel visual inicialmente.

O histórico do GitHub Actions deverá permitir consultar as execuções anteriores.

## 10. Estrutura sugerida do projeto

Organize o repositório de forma profissional.

Exemplo:

```text
point-perucaba-stories/
│
├── .github/
│   └── workflows/
│       └── daily-story.yml
│
├── assets/
│   └── stories/
│       ├── segunda.jpg
│       ├── terca.jpg
│       ├── quarta.jpg
│       ├── quinta.jpg
│       ├── sexta.jpg
│       ├── sabado.jpg
│       └── domingo.jpg
│
├── src/
│   ├── config.py
│   ├── scheduler.py
│   ├── image_selector.py
│   ├── image_validator.py
│   ├── meta_client.py
│   ├── publisher.py
│   ├── publication_log.py
│   └── main.py
│
├── tests/
│   ├── test_image_selector.py
│   ├── test_image_validator.py
│   ├── test_scheduler.py
│   └── test_publisher.py
│
├── requirements.txt
├── .gitignore
├── README.md
└── .env.example
```

A estrutura poderá ser ajustada conforme a necessidade técnica, sem criar abstrações desnecessárias.

## 11. Testes obrigatórios

Implemente testes unitários para:

1. Identificação correta dos sete dias da semana.
2. Seleção da imagem correspondente.
3. Comportamento diante de imagem inexistente.
4. Validação de formato e tamanho.
5. Conversão correta de fuso horário.
6. Prevenção de duplicidade.
7. Tratamento de erros da API.
8. Execução em modo simulação.

Utilize mocks para testar a integração com a Meta sem publicar Stories reais.

A execução em modo de simulação não poderá criar containers ou publicar mídias na Meta.

## 12. Segurança

- Não inserir tokens no código.
- Não inserir senhas no README.
- Não enviar arquivos `.env` ao GitHub.
- Utilizar GitHub Secrets.
- Aplicar permissões mínimas ao workflow.
- Não expor informações privadas nos logs.
- Fixar versões de dependências.
- Utilizar tratamento seguro de exceções.
- Não executar comandos destrutivos automaticamente.

## 13. Documentação

Crie um README em português brasileiro.

O documento deverá explicar:

1. Objetivo do projeto.
2. Arquitetura.
3. Tecnologias utilizadas.
4. Como funciona o calendário semanal.
5. Como adicionar ou substituir imagens.
6. Como configurar o GitHub Pages, se utilizado.
7. Como configurar os Secrets.
8. Como configurar o aplicativo na Meta.
9. Como obter o Instagram Business Account ID.
10. Como configurar o token de acesso.
11. Como executar manualmente.
12. Como verificar o histórico de publicações.
13. Como corrigir erros.
14. Como renovar credenciais.
15. Limitações do agendamento do GitHub Actions.

## 14. Processo de desenvolvimento

Não implemente tudo de uma vez sem validar a arquitetura.

Trabalhe nas seguintes fases:

### Fase 1 — Análise e planejamento
- Consultar documentações oficiais.
- Definir arquitetura.
- Identificar limitações da Meta.
- Identificar limitações do GitHub Actions.
- Definir hospedagem gratuita das imagens.
- Apresentar estrutura do projeto.

### Fase 2 — Estrutura inicial
- Criar os arquivos.
- Implementar configurações.
- Implementar seleção de imagens.
- Implementar validações.
- Criar testes unitários.

### Fase 3 — Integração com Meta
- Implementar autenticação.
- Implementar cliente HTTP.
- Implementar criação do container.
- Implementar publicação.
- Implementar tratamento de respostas.

### Fase 4 — Automação
- Criar workflow do GitHub Actions.
- Configurar execução diária.
- Configurar execução manual.
- Implementar controle de duplicidade.
- Implementar logs.

### Fase 5 — Testes e validação
- Executar testes.
- Validar URLs das imagens.
- Testar autenticação.
- Executar simulação.
- Realizar uma publicação real somente depois de autorização expressa do proprietário.

### Fase 6 — Entrega
- Atualizar README.
- Documentar configurações.
- Listar Secrets necessários.
- Apresentar checklist de implantação.
- Demonstrar como substituir as sete imagens.

## 15. Regras de trabalho

Quero que você atue como engenheiro responsável pelo projeto.

Siga estas regras:

1. Não invente informações técnicas.
2. Consulte documentação oficial antes de implementar integrações externas.
3. Prefira soluções simples, gratuitas e sustentáveis.
4. Não introduza bibliotecas desnecessárias.
5. Não crie dependências pagas.
6. Não publique nada no Instagram sem autorização expressa.
7. Não solicite que o proprietário envie tokens ou senhas pelo chat.
8. Não considere o projeto concluído apenas porque o workflow foi criado.
9. Não esconda limitações técnicas.
10. Documente decisões arquiteturais importantes.

Se uma decisão depender de configuração manual do proprietário, interrompa a execução naquela etapa e apresente instruções claras, com o caminho exato na interface.

Não peça informações que possam ser obtidas diretamente pela documentação ou pela inspeção do repositório.

## 16. Critérios de conclusão

O projeto será considerado concluído quando:

- O código estiver implementado.
- Os testes estiverem passando.
- O workflow estiver configurado.
- O agendamento diário estiver correto.
- A seleção das sete imagens estiver validada.
- A autenticação estiver funcionando.
- Uma publicação real de teste tiver sido autorizada e concluída.
- O controle de duplicidade estiver implementado.
- O README estiver atualizado.

Comece pela Fase 1.

Antes de modificar arquivos ou criar integrações, apresente a arquitetura proposta, as dependências externas, os custos (que devem ser zero) e os riscos identificados.

Aguarde a validação da arquitetura antes de avançar para a implementação completa.