// Carregar modelos quando a página carregar
document.addEventListener('DOMContentLoaded', async function() {
    try {
        const response = await fetch('/api/modelos-termo');
        if (!response.ok) {
            throw new Error('Erro ao carregar modelos');
        }
        
        const modelos = await response.json();
        
        const selectModelo = document.getElementById('modelo');
        // Limpar opções existentes
        selectModelo.innerHTML = '<option value="">Selecione um modelo...</option>';
        
        // Adicionar novos modelos
        if (Array.isArray(modelos)) {
            modelos.forEach(modelo => {
                const option = document.createElement('option');
                option.value = modelo._id;
                option.textContent = modelo.nome || 'Modelo sem nome';
                option.dataset.titulo = modelo.titulo || '';
                option.dataset.tipo = modelo.tipo || '';
                selectModelo.appendChild(option);
            });
        }
        
        // Preencher a data atual
        const hoje = new Date();
        const dataFormatada = hoje.toISOString().split('T')[0];
        document.getElementById('data_documento').value = dataFormatada;
        
    } catch (error) {
        console.error('Erro ao carregar modelos:', error);
        Swal.fire({
            title: 'Erro!',
            text: 'Erro ao carregar modelos. Por favor, recarregue a página.',
            icon: 'error',
            confirmButtonText: 'OK',
            confirmButtonColor: '#dc3545'
        });
    }
});

// Atualizar título quando selecionar modelo
document.getElementById('modelo').addEventListener('change', function() {
    const selectedOption = this.options[this.selectedIndex];
    const tituloInput = document.getElementById('titulo_documento');
    if (selectedOption.value) {
        const titulo = selectedOption.dataset.titulo || selectedOption.textContent;
        tituloInput.value = titulo;
    } else {
        tituloInput.value = '';
    }
});

// Exemplos de preenchimento
const exemplos = {
    'exemplo1': {
        'nome_colaborador': 'João Silva',
        'departamento': 'TI',
        'cargo': 'Desenvolvedor',
        'marca_equipamento': 'Dell',
        'modelo_equipamento': 'Latitude 5420',
        'numero_tag': 'TAG123456',
        'numero_patrimonio': 'PAT789012',
        'caracteristicas': 'Intel i7, 16GB RAM, 512GB SSD',
        'interfaces': 'USB 3.0, HDMI, RJ45',
        'acessorios': 'Mouse, Teclado, Carregador'
    },
    'exemplo2': {
        'nome_colaborador': 'Maria Santos',
        'departamento': 'Marketing',
        'cargo': 'Analista',
        'marca_equipamento': 'HP',
        'modelo_equipamento': 'EliteBook 840',
        'numero_tag': 'TAG654321',
        'numero_patrimonio': 'PAT098765',
        'caracteristicas': 'Intel i5, 8GB RAM, 256GB SSD',
        'interfaces': 'USB-C, DisplayPort, Wi-Fi 6',
        'acessorios': 'Dock Station, Monitor Externo'
    }
};

// Função para preencher o formulário com exemplo
function preencherExemplo(numeroExemplo) {
    const exemplo = exemplos[`exemplo${numeroExemplo}`];
    if (exemplo) {
        Object.keys(exemplo).forEach(campo => {
            const elemento = document.getElementById(campo);
            if (elemento) {
                elemento.value = exemplo[campo];
            }
        });
    }
}

// Função para limpar o formulário
function limparFormulario() {
    document.getElementById('formNovoTermo').reset();
    const hoje = new Date();
    const dataFormatada = hoje.toISOString().split('T')[0];
    document.getElementById('data_documento').value = dataFormatada;
}

async function salvarTermo(event) {
    event.preventDefault();
    
    const loaderContainer = document.querySelector('.loader-container');
    const loaderMessage = document.querySelector('.loader-message');
    
    try {
        const modeloId = document.getElementById('modelo').value;
        if (!modeloId) {
            await Swal.fire({
                title: 'Erro!',
                text: 'Por favor, selecione um modelo',
                icon: 'error',
                confirmButtonText: 'OK',
                confirmButtonColor: '#dc3545'
            });
            return;
        }

        // Mostrar loader
        loaderMessage.textContent = 'Gerando termo e convertendo para PDF...';
        loaderContainer.style.display = 'flex';
        
        // Coletar dados do formulário
        const formData = new FormData();
        formData.append('modelo_id', modeloId);
        
        // Coletar todos os campos do formulário
        const campos = {
            titulo_documento: document.getElementById('titulo_documento').value,
            nome_colaborador: document.getElementById('nome_colaborador').value,
            departamento: document.getElementById('departamento').value,
            cargo: document.getElementById('cargo').value,
            marca_equipamento: document.getElementById('marca_equipamento').value,
            modelo_equipamento: document.getElementById('modelo_equipamento').value,
            numero_tag: document.getElementById('numero_tag').value,
            numero_patrimonio: document.getElementById('numero_patrimonio').value,
            caracteristicas: document.getElementById('caracteristicas').value,
            interfaces: document.getElementById('interfaces').value,
            acessorios: document.getElementById('acessorios').value,
            data_documento: document.getElementById('data_documento').value,
            dia_mesescrito_ano: new Date().toLocaleDateString('pt-BR', { 
                day: 'numeric',
                month: 'long',
                year: 'numeric'
            })
        };
        
        formData.append('dados_termo', JSON.stringify(campos));
        
        const response = await fetch('/api/processar-termo', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        // Esconder loader antes de mostrar o SweetAlert
        loaderContainer.style.display = 'none';

        if (data.success) {
            await Swal.fire({
                title: 'Sucesso!',
                text: 'Termo criado com sucesso!',
                icon: 'success',
                confirmButtonText: 'OK',
                confirmButtonColor: '#28a745'
            });
            window.location.href = '/';
        } else {
            throw new Error(data.message || 'Erro ao processar termo');
        }
    } catch (error) {
        // Esconder loader antes de mostrar o erro
        loaderContainer.style.display = 'none';
        
        await Swal.fire({
            title: 'Erro!',
            text: 'Erro ao criar termo: ' + error.message,
            icon: 'error',
            confirmButtonText: 'OK',
            confirmButtonColor: '#dc3545'
        });
    }
}

// Adicionar event listeners quando o DOM estiver carregado
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('formNovoTermo');
    if (form) {
        form.addEventListener('submit', salvarTermo);
    }
});

// Função para mostrar notificações
function showNotification(message, type) {
    // Remover notificações anteriores
    const notificacoesAnteriores = document.querySelectorAll('.alert');
    notificacoesAnteriores.forEach(notificacao => notificacao.remove());
    
    // Criar nova notificação
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Adicionar ao topo da página
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // Remover após 10 segundos
    setTimeout(() => {
        if (alertDiv && alertDiv.parentElement) {
            alertDiv.remove();
        }
    }, 10000);
}

// Função para atualizar a lista de termos recentes
async function atualizarTermosRecentes() {
    try {
        const response = await fetch('/api/termos');
        const data = await response.json();
        
        if (data.success) {
            const termosRecentes = document.getElementById('termosTableBody');
            if (termosRecentes && data.termos) {
                // Atualizar a tabela com os novos dados
                termosRecentes.innerHTML = data.termos.map(termo => `
                    <tr>
                        <td>${termo.dados.titulo_documento || ''}</td>
                        <td>${termo.dados.nome_colaborador || ''}</td>
                        <td>${termo.dados.data_documento || ''}</td>
                        <td>${termo.data_assinatura || '-'}</td>
                        <td>
                            ${termo.status === "Assinado" 
                                ? `<span class="status-badge status-assinado">${termo.status}</span>`
                                : `<span class="status-badge status-pendente">Pendente de Assinatura</span>`
                            }
                        </td>
                        <td>
                            <button class="btn btn-sm btn-primary" onclick="gerarLinkAssinatura('${termo._id}')">
                                <i class="bi bi-link-45deg"></i>
                            </button>
                            <button class="btn btn-sm btn-secondary" onclick="visualizarTermo('${termo._id}')">
                                <i class="bi bi-eye"></i>
                            </button>
                        </td>
                    </tr>
                `).join('');
            }
        }
    } catch (error) {
        console.error('Erro ao atualizar termos recentes:', error);
    }
}
