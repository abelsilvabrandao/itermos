// Variáveis globais
let termos = []; // Armazena todos os termos
let filteredTermos = []; // Armazena termos filtrados

// Função para carregar os termos
async function carregarTermos() {
    console.log('Função carregarTermos chamada');
    try {
        console.log('Iniciando carregamento de termos...');
        const response = await fetch('/api/listar-termos');
        console.log('Requisição enviada para /api/listar-termos');
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `Erro ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('Dados recebidos:', data);
        
        if (data.success) {
            termos = data.termos || [];
            console.log(`${termos.length} termos carregados`);
            aplicarFiltros(); // Aplica filtros e atualiza a tabela
        } else {
            throw new Error(data.error || 'Erro desconhecido ao carregar termos');
        }
    } catch (error) {
        console.error('Erro ao carregar termos:', error);
        showNotification('Erro ao carregar termos: ' + error.message, 'danger');
        // Mostrar mensagem de erro na tabela
        const tbody = document.getElementById('listaTermos');
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center text-danger">
                    <i class="bi bi-exclamation-triangle"></i>
                    Erro ao carregar termos: ${error.message}
                </td>
            </tr>
        `;
    }
}

// Função para aplicar filtros
function aplicarFiltros() {
    const tipo = document.getElementById('filtroTipo').value;
    const status = document.getElementById('filtroStatus').value;
    const busca = document.getElementById('busca').value.toLowerCase();
    
    filteredTermos = termos.filter(termo => {
        const matchTipo = !tipo || termo.tipo === tipo;
        const matchStatus = !status || termo.status === status;
        const matchBusca = !busca || 
            termo.nome_colaborador.toLowerCase().includes(busca) || 
            termo.modelo_notebook.toLowerCase().includes(busca);
        
        return matchTipo && matchStatus && matchBusca;
    });
    
    atualizarTabela();
}

// Função para atualizar a tabela
function atualizarTabela() {
    const tbody = document.getElementById('listaTermos');
    tbody.innerHTML = '';
    
    if (filteredTermos.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center">
                    <i class="bi bi-info-circle"></i>
                    Nenhum termo encontrado
                </td>
            </tr>
        `;
        return;
    }
    
    filteredTermos.forEach(termo => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${termo.data_criacao}</td>
            <td>${termo.nome_colaborador}</td>
            <td>
                <span class="badge ${getBadgeClass(termo.tipo)}">
                    ${getTipoLabel(termo.tipo)}
                </span>
            </td>
            <td>${termo.modelo_notebook}</td>
            <td>
                <span class="badge ${getStatusBadgeClass(termo.status)}">
                    ${getStatusLabel(termo.status)}
                </span>
            </td>
            <td>
                <div class="btn-group">
                    <button class="btn btn-sm btn-primary" onclick="baixarPDF('${termo._id}')" title="Baixar PDF">
                        <i class="bi bi-file-pdf"></i>
                    </button>
                    ${termo.status === 'pendente' ? `
                        <button class="btn btn-sm btn-success" onclick="gerarLink('${termo._id}')" title="Gerar Link para Assinatura">
                            <i class="bi bi-link-45deg"></i>
                        </button>
                    ` : ''}
                    ${termo.status === 'assinado' && termo.tipo === 'entrega' && !termo.tem_devolucao ? `
                        <button class="btn btn-sm btn-warning" onclick="gerarDevolucao('${termo._id}')" title="Gerar Devolução">
                            <i class="bi bi-box-arrow-left"></i>
                        </button>
                    ` : ''}
                    <button class="btn btn-sm btn-danger" onclick="deletarTermo('${termo._id}')" title="Excluir Termo">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// Funções auxiliares
function getBadgeClass(tipo) {
    const classes = {
        'entrega': 'bg-primary',
        'devolucao': 'bg-warning',
        'emprestimo': 'bg-info'
    };
    return classes[tipo] || 'bg-secondary';
}

function getStatusBadgeClass(status) {
    return status === 'assinado' ? 'bg-success' : 'bg-warning';
}

function getTipoLabel(tipo) {
    const labels = {
        'entrega': 'Entrega',
        'devolucao': 'Devolução',
        'emprestimo': 'Empréstimo'
    };
    return labels[tipo] || tipo;
}

function getStatusLabel(status) {
    const labels = {
        'pendente': 'Pendente',
        'assinado': 'Assinado'
    };
    return labels[status] || status;
}

// Funções de ação
async function baixarPDF(id) {
    try {
        window.open(`/api/gerar-termo/${id}`, '_blank');
    } catch (error) {
        showNotification('Erro ao baixar PDF: ' + error.message, 'danger');
    }
}

async function deletarTermo(id) {
    if (!confirm('Tem certeza que deseja excluir este termo? Esta ação não pode ser desfeita.')) {
        return;
    }

    try {
        const response = await fetch(`/api/deletar-termo/${id}`, {
            method: 'DELETE'
        });
        console.log('Requisição enviada para /api/deletar-termo/:id');
        const data = await response.json();
        
        if (data.success) {
            showNotification('Termo excluído com sucesso!', 'success');
            carregarTermos(); // Recarrega a lista
        } else {
            showNotification('Erro ao excluir termo: ' + data.detail, 'danger');
        }
    } catch (error) {
        showNotification('Erro ao excluir termo: ' + error.message, 'danger');
    }
}

async function gerarLink(id) {
    try {
        const response = await fetch(`/api/gerar-link-assinatura/${id}`);
        console.log('Requisição enviada para /api/gerar-link-assinatura/:id');
        const data = await response.json();
        
        if (data.success) {
            const linkAssinatura = document.getElementById('linkAssinatura');
            linkAssinatura.value = data.link;
            new bootstrap.Modal(document.getElementById('modalLink')).show();
        } else {
            showNotification('Erro ao gerar link: ' + data.detail, 'danger');
        }
    } catch (error) {
        showNotification('Erro ao gerar link: ' + error.message, 'danger');
    }
}

function copiarLink() {
    const input = document.getElementById('linkAssinatura');
    input.select();
    document.execCommand('copy');
    showNotification('Link copiado para a área de transferência!', 'success');
}

async function gerarDevolucao(id) {
    if (!confirm('Tem certeza que deseja gerar um termo de devolução?')) {
        return;
    }

    try {
        const response = await fetch(`/api/gerar-devolucao/${id}`, {
            method: 'POST'
        });
        console.log('Requisição enviada para /api/gerar-devolucao/:id');
        const data = await response.json();
        
        if (data.success) {
            showNotification('Termo de devolução gerado com sucesso!', 'success');
            carregarTermos(); // Recarrega a lista
        } else {
            showNotification('Erro ao gerar devolução: ' + data.detail, 'danger');
        }
    } catch (error) {
        showNotification('Erro ao gerar devolução: ' + error.message, 'danger');
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Adicionar listeners aos filtros
    document.getElementById('busca').addEventListener('input', aplicarFiltros);
    document.getElementById('filtroTipo').addEventListener('change', aplicarFiltros);
    document.getElementById('filtroStatus').addEventListener('change', aplicarFiltros);

    // Carregar termos iniciais
    carregarTermos();
});
