// Função para log
function log(message, type = 'info') {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] [${type}] ${message}`);
    
    if (type === 'error') {
        console.error(message);
    }
}

async function cadastrarModelo(event) {
    event.preventDefault();
    
    // Mostrar indicador de carregamento
    const submitButton = document.querySelector('button[type="submit"]');
    const originalText = submitButton.innerHTML;
    submitButton.disabled = true;
    submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Salvando...';

    const formData = new FormData(event.target);
    
    try {
        const response = await fetch('/api/cadastrar-modelo', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if (data.success) {
            alert('Modelo cadastrado com sucesso!');
            window.location.href = '/';  // ou redirecione para onde desejar
        } else {
            alert('Erro ao cadastrar modelo: ' + data.message);
        }
    } catch (error) {
        alert('Erro ao cadastrar modelo: ' + error.message);
    } finally {
        // Restaurar botão ao estado original
        submitButton.disabled = false;
        submitButton.innerHTML = originalText;
    }
}



// Função para mostrar notificação
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show notification`;
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Adicionar ao container de notificações
    const container = document.getElementById('notificationContainer') || document.body;
    container.appendChild(notification);
    
    // Auto-remover após 5 segundos
    setTimeout(() => {
        notification.remove();
    }, 5000);
}


// Função para excluir modelo
async function excluirModelo(modeloId) {
    if (!confirm('Tem certeza que deseja excluir este modelo?')) {
        return;
    }
    
    try {
        log(`Excluindo modelo ${modeloId}...`);
        const response = await fetch(`/api/excluir-modelo/${modeloId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error(`Erro ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        if (result.success) {
            showNotification('Modelo excluído com sucesso!');
            await carregarModelos();
        } else {
            throw new Error(result.detail || 'Erro ao excluir modelo');
        }
    } catch (error) {
        log('Erro ao excluir modelo: ' + error.message, 'error');
        showNotification(error.message, 'danger');
    }
}

// Handler para o formulário de cadastro de modelo
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('formCadastroModelo');
    if (form) {
        // Carregar modelos ao iniciar a página
        carregarModelos();
        
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            try {
                log('Iniciando envio do formulário...');
                
                const formData = new FormData(form);
                const submitButton = form.querySelector('button[type="submit"]');
                const arquivo = formData.get('arquivo_rtf');
                
                // Validações do arquivo
                if (!arquivo || arquivo.size === 0) {
                    throw new Error('Por favor, selecione um arquivo RTF válido');
                }
                
                if (!arquivo.name.toLowerCase().endsWith('.rtf')) {
                    throw new Error('O arquivo deve estar no formato RTF');
                }
                
                log(`Arquivo selecionado: ${arquivo.name} (${arquivo.size} bytes)`);
                
                // Desabilitar botão e mostrar loading
                submitButton.disabled = true;
                submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Enviando...';
                
                // Log dos dados do formulário
                log('=== Dados do Formulário ===');
                for (let [key, value] of formData.entries()) {
                    if (key !== 'arquivo_rtf') {
                        log(`Campo ${key}: ${value}`);
                    } else {
                        log(`Campo ${key}: ${value.name} (${value.size} bytes)`);
                    }
                }
                
                // Fazer requisição
                log('Iniciando upload do arquivo...');
                const response = await fetch('/api/cadastrar-modelo', {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'Accept': 'application/json'
                    }
                });
                
                // Verificar tipo de conteúdo
                const contentType = response.headers.get('content-type');
                log(`Tipo de conteúdo da resposta: ${contentType}`);
                
                if (!response.ok) {
                    if (contentType && contentType.includes('application/json')) {
                        const errorData = await response.json();
                        throw new Error(errorData.detail || `Erro ${response.status}: ${response.statusText}`);
                    } else {
                        const text = await response.text();
                        log('Resposta não-JSON recebida:', 'error');
                        log(text, 'error');
                        throw new Error(`Erro ${response.status}: ${response.statusText || 'Resposta inválida do servidor'}`);
                    }
                }
                
                if (contentType && contentType.includes('application/json')) {
                    const result = await response.json();
                    log('Resposta JSON recebida:', 'info');
                    console.log(result);
                    
                    if (result.success) {
                        showNotification(result.message || 'Modelo cadastrado com sucesso!');
                        form.reset();
                        // Recarregar lista de modelos após cadastro
                        await carregarModelos();
                    } else {
                        throw new Error(result.detail || 'Erro desconhecido ao cadastrar modelo');
                    }
                } else {
                    const text = await response.text();
                    log('Resposta não-JSON recebida:', 'error');
                    log(text, 'error');
                    throw new Error('Servidor retornou uma resposta em formato inválido');
                }
                
            } catch (error) {
                log('ERRO: ' + error.message, 'error');
                console.error('Stack trace:', error);
                showNotification(error.message, 'danger');
            } finally {
                // Restaurar botão
                const submitButton = form.querySelector('button[type="submit"]');
                submitButton.disabled = false;
                submitButton.innerHTML = '<i class="bi bi-upload"></i> Cadastrar Modelo';
            }
        });
    }
});

function renderizarTermo(termo) {
    return `
        <tr>
            <td>${termo.titulo_documento || 'Não definido'}</td>
            <td>${termo.nome_colaborador || 'Não informado'}</td>
            <td>${formatarData(termo.data_documento)}</td>
            <td>${termo.data_assinatura ? formatarData(termo.data_assinatura) : 'Não assinada'}</td>
            <td>
                <span class="badge ${termo.status === 'Pendente' ? 'bg-warning' : 'bg-success'}">
                    ${termo.status}
                </span>
            </td>
            <td>
                <div class="btn-group">
                    <button class="btn btn-primary btn-sm" onclick="gerarLink('${termo._id}')" title="Copiar link">
                        <i class="bi bi-link-45deg"></i> Link
                    </button>
                    <button class="btn btn-info btn-sm" onclick="mostrarQRCode('${termo._id}')" title="Gerar QR Code">
                        <i class="bi bi-qr-code"></i> QR
                    </button>
                    <button class="btn btn-secondary btn-sm" onclick="window.open('/api/download-termo-pdf/${termo._id}', '_blank')" title="Visualizar PDF">
                        <i class="bi bi-eye"></i> Visualizar
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="excluirTermo('${termo._id}')" title="Excluir termo">
                        <i class="bi bi-trash"></i> Excluir
                    </button>
                </div>
            </td>
        </tr>
    `;
}

function formatarData(data) {
    if (!data || data.includes("não disponível") || data.includes("Não assinada")) {
        return data;  // Mantém como já está vindo do backend
    }
    try {
        return new Date(data).toLocaleDateString("pt-BR");
    } catch (e) {
        return "Data inválida";
    }
}

// Atualizar a função carregarTermos para melhor tratamento de erro
async function carregarTermos() {
    // Verificar se estamos na página que contém a tabela de termos
    const termosTableBody = document.getElementById('termosTableBody');
    if (!termosTableBody) {
        // Se não estamos na página de termos, simplesmente retornar
        return;
    }

    try {
        const response = await fetch('/api/listar-termos');
        const data = await response.json();
        const tbody = document.getElementById('termosTableBody');
        tbody.innerHTML = '';

        data.forEach(termo => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${termo.dados.titulo_documento || ''}</td>
                <td>${termo.dados.nome_colaborador || ''}</td>
                <td>${termo.dados.data_documento || ''}</td>
                <td>${termo.data_assinatura || 'Não assinada'}</td>
                <td>
                    ${termo.status === 'Assinado' 
                        ? '<span class="status-badge status-assinado">Assinado</span>'
                        : '<span class="status-badge status-pendente">Pendente de Assinatura</span>'
                    }
                </td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="gerarLinkAssinatura('${termo._id}')">
                        <i class="bi bi-link-45deg"></i> Link
                    </button>
                    <button class="btn btn-sm btn-info" onclick="gerarQRCode('${termo._id}')">
                        <i class="bi bi-qr-code"></i> QR
                    </button>
                    <button class="btn btn-sm btn-secondary" onclick="visualizarTermo('${termo._id}')">
                        <i class="bi bi-eye"></i> Visualizar
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="excluirTermo('${termo._id}')">
                        <i class="bi bi-trash"></i> Excluir
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (error) {
        console.error('Erro ao carregar termos:', error);
        if (termosTableBody) {
            termosTableBody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Erro ao carregar termos</td></tr>';
        }
    }
}

// Carregar termos apenas quando estiver na página principal
document.addEventListener('DOMContentLoaded', function() {
    // Verificar se estamos na página que contém a tabela de termos
    if (document.getElementById('termosTableBody')) {
        carregarTermos();
    }
});

async function downloadTermoPDF(termoId) {
    try {
        const response = await fetch(`/api/download-termo-pdf/${termoId}`);
        if (!response.ok) throw new Error('Erro ao baixar PDF');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `termo-${termoId}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Erro ao baixar PDF:', error);
        alert('Erro ao baixar o PDF do termo');
    }
}

// Função para aplicar filtros (implementar conforme necessário)
function aplicarFiltros() {
    const tipo = document.getElementById('filtroTipo').value;
    const status = document.getElementById('filtroStatus').value;
    const busca = document.getElementById('busca').value;
    
    console.log('Aplicando filtros:', { tipo, status, busca });
    // Implementar lógica de filtro aqui
    carregarTermos();
}

async function excluirTermo(termoId) {
    if (!confirm("Você tem certeza que deseja excluir este termo?")) {
        return; // Se o usuário cancelar, não faz nada
    }
    
    try {
        const response = await fetch(`/api/deletar-termo/${termoId}`, {
            method: 'DELETE',
        });
        const data = await response.json();
        if (data.success) {
            alert('Termo excluído com sucesso!');
            carregarTermos(); // Recarrega a lista de termos
        } else {
            alert(data.detail);
        }
    } catch (error) {
        console.error('Erro ao excluir termo:', error);
        alert('Erro ao excluir termo. Veja o console para mais detalhes.');
    }
}

// Função para gerar link de assinatura
async function gerarLinkAssinatura(termoId) {
    try {
        // Criar um elemento de input temporário
        const tempInput = document.createElement('input');
        tempInput.value = `${window.location.origin}/assinar-termo/${termoId}`;
        document.body.appendChild(tempInput);
        
        // Selecionar e copiar o texto
        tempInput.select();
        document.execCommand('copy');
        
        // Remover o input temporário
        document.body.removeChild(tempInput);
        
        alert('Link copiado para a área de transferência!');
    } catch (error) {
        console.error('Erro ao gerar link:', error);
        alert('Erro ao gerar link de assinatura.');
    }
}

// Função para visualizar termo
function visualizarTermo(termoId) {
    window.location.href = `/visualizar-termo/${termoId}`;
}

// Função para gerar QR Code
async function gerarQRCode(termoId) {
    try {
        const url = `${window.location.origin}/assinar-termo/${termoId}`;
        
        // Criar modal para exibir o QR Code
        const modal = document.createElement('div');
        modal.style.position = 'fixed';
        modal.style.top = '0';
        modal.style.left = '0';
        modal.style.width = '100%';
        modal.style.height = '100%';
        modal.style.backgroundColor = 'rgba(0,0,0,0.5)';
        modal.style.display = 'flex';
        modal.style.alignItems = 'center';
        modal.style.justifyContent = 'center';
        modal.style.zIndex = '1000';
        
        const modalContent = document.createElement('div');
        modalContent.style.backgroundColor = 'white';
        modalContent.style.padding = '20px';
        modalContent.style.borderRadius = '8px';
        modalContent.style.textAlign = 'center';
        
        const qrCanvas = document.createElement('canvas');
        modalContent.appendChild(qrCanvas);
        
        const closeButton = document.createElement('button');
        closeButton.textContent = 'Fechar';
        closeButton.className = 'btn btn-secondary mt-3';
        closeButton.onclick = () => document.body.removeChild(modal);
        modalContent.appendChild(closeButton);
        
        modal.appendChild(modalContent);
        document.body.appendChild(modal);
        
        // Gerar QR Code
        QRCode.toCanvas(qrCanvas, url, { width: 256 }, function (error) {
            if (error) {
                console.error('Erro ao gerar QR Code:', error);
                alert('Erro ao gerar QR Code.');
                document.body.removeChild(modal);
            }
        });
        
    } catch (error) {
        console.error('Erro ao gerar QR Code:', error);
        alert('Erro ao gerar QR Code.');
    }
}

// Carrega os termos quando a página estiver totalmente pronta
window.addEventListener('load', function() {
    console.log('Página totalmente carregada');
    carregarTermos();
});

function renderStatus(status) {
    if (status === 'Assinado') {
        return `<span class="status-badge status-assinado">Assinado</span>`;
    } else {
        return `<span class="status-badge status-pendente">Pendente de Assinatura</span>`;
    }
}

function atualizarTabelaTermos(termos) {
    const tbody = document.getElementById('termosTableBody');
    tbody.innerHTML = '';

    termos.forEach(termo => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${termo.nome}</td>
            <td>${termo.colaborador}</td>
            <td>${termo.data_documento}</td>
            <td>${termo.data_assinatura || 'Não assinada'}</td>
            <td>${renderStatus(termo.status)}</td>
            <td>
                <button class="btn btn-sm btn-primary" onclick="gerarLinkAssinatura('${termo._id}')">
                    <i class="bi bi-link-45deg"></i>
                </button>
                <button class="btn btn-sm btn-info" onclick="gerarQRCode('${termo._id}')">
                    <i class="bi bi-qr-code"></i>
                </button>
                <button class="btn btn-sm btn-secondary" onclick="visualizarTermo('${termo._id}')">
                    <i class="bi bi-eye"></i>
                </button>
                <button class="btn btn-sm btn-danger" onclick="excluirTermo('${termo._id}')">
                    <i class="bi bi-trash"></i>
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// Função para gerar QR Code
async function gerarQRCode(termoId) {
    try {
        const url = `${window.location.origin}/assinar-termo/${termoId}`;
        
        // Criar modal para exibir o QR Code
        const modal = document.createElement('div');
        modal.style.position = 'fixed';
        modal.style.top = '0';
        modal.style.left = '0';
        modal.style.width = '100%';
        modal.style.height = '100%';
        modal.style.backgroundColor = 'rgba(0,0,0,0.5)';
        modal.style.display = 'flex';
        modal.style.alignItems = 'center';
        modal.style.justifyContent = 'center';
        modal.style.zIndex = '1000';
        
        const modalContent = document.createElement('div');
        modalContent.style.backgroundColor = 'white';
        modalContent.style.padding = '20px';
        modalContent.style.borderRadius = '8px';
        modalContent.style.textAlign = 'center';
        
        const qrCanvas = document.createElement('canvas');
        modalContent.appendChild(qrCanvas);
        
        const closeButton = document.createElement('button');
        closeButton.textContent = 'Fechar';
        closeButton.className = 'btn btn-secondary mt-3';
        closeButton.onclick = () => document.body.removeChild(modal);
        modalContent.appendChild(closeButton);
        
        modal.appendChild(modalContent);
        document.body.appendChild(modal);
        
        // Gerar QR Code
        QRCode.toCanvas(qrCanvas, url, { width: 256 }, function (error) {
            if (error) {
                console.error('Erro ao gerar QR Code:', error);
                alert('Erro ao gerar QR Code.');
                document.body.removeChild(modal);
            }
        });
        
    } catch (error) {
        console.error('Erro ao gerar QR Code:', error);
        alert('Erro ao gerar QR Code.');
    }
}

// Função para deletar termo
async function deletarTermo(termoId) {
    if (!confirm('Tem certeza que deseja deletar este termo?')) {
        return;
    }

    try {
        const response = await fetch(`/api/excluir-termo/${termoId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        if (data.success) {
            // Recarregar a página para atualizar a lista
            window.location.reload();
        } else {
            alert('Erro ao deletar termo: ' + data.message);
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao deletar termo');
    }
}

// Função para devolver termo
async function devolverTermo(termoId) {
    try {
        const response = await fetch(`/api/gerar-termo-devolucao/${termoId}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        if (data.success) {
            alert('Termo de devolução gerado com sucesso!');
            window.location.reload();
        } else {
            alert('Erro ao gerar termo de devolução: ' + data.message);
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao gerar termo de devolução');
    }
}

// Função para gerar link de assinatura
async function gerarLinkAssinatura(termoId) {
    try {
        // Criar o link de assinatura
        const url = `${window.location.origin}/assinar-termo/${termoId}`;
        
        // Copiar para a área de transferência
        await navigator.clipboard.writeText(url);
        
        // Mostrar mensagem de sucesso
        alert('Link copiado para a área de transferência!');
    } catch (error) {
        console.error('Erro ao gerar link:', error);
        alert('Erro ao gerar link de assinatura');
    }
}

// Função para visualizar termo
function visualizarTermo(termoId) {
    window.location.href = `/visualizar-termo/${termoId}`;
}