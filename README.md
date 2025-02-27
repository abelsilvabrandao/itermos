# Sistema de Documentação TI

Sistema para controle de documentação de TI, focado no gerenciamento de termos de responsabilidade e devolução de desktop e notebooks.

## Funcionalidades

- Criação de diferentes tipos de termos:
  - Termo de Responsabilidade Notebook/Desktop
  - Termo de Responsabilidade Notebook/Desktop (Empréstimo)
  - Termo de Devolução Notebook/Desktop
- Criar novo termo (novo-termo)
- Busca por nome do colaborador (em Index.html)
- O Preenchimento automático do termo de devolução com base no termo de entrega
- Armazenamento e consulta em MongoDB

## Requisitos

- Python 3.8+
- MongoDB
- Pip (gerenciador de pacotes Python)


## Estrutura do Projeto

- `main.py`: Arquivo principal com as rotas e lógica do backend
- `templates/`: Pasta com os templates HTML
  - `index.html`: Página inicial com busca dos termos
  - `novo_termo.html`: Formulário para criar novos termos (Utilizará os modelos cadastrados em RTF)
- `requirements.txt`: Dependências do projeto
- `.env`: Configurações do ambiente
