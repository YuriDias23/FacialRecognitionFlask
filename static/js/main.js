document.addEventListener('DOMContentLoaded', () => {
    fetch('/get_data')
        .then(response => response.json())
        .then(data => {
            const cameraList = document.getElementById('camera-list');
            const webhookList = document.getElementById('webhook-list');

            data.cameras.forEach(camera => {
                const option = document.createElement('option');
                option.value = camera[0];
                option.textContent = camera[1];
                cameraList.appendChild(option);
            });

            data.webhooks.forEach(webhook => {
                const option = document.createElement('option');
                option.value = webhook[0];
                option.textContent = webhook[1];
                webhookList.appendChild(option);
            });
        });
});

function editCamera() {
    const id = document.getElementById('camera-list').value;
    const newName = prompt("Novo nome da câmera:");
    const newUrl = prompt("Novo URL da câmera:");
    const newUser = prompt("Novo usuário da câmera:");
    const newPass = prompt("Nova senha da câmera:");

    if (id && newName && newUrl) {
        fetch('/edit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `type=camera&id=${id}&name=${newName}&username=${newUser}&password=${newPass}&url=${newUrl}`
        }).then(response => response.json()).then(data => alert(data.message));
    }
}

function deleteCamera() {
    const id = document.getElementById('camera-list').value;
    if (id && confirm("Deseja realmente excluir esta câmera?")) {
        fetch('/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `type=camera&id=${id}`
        }).then(response => response.json()).then(data => alert(data.message));
    }
}

function editWebhook() {
    const id = document.getElementById('webhook-list').value;
    const newName = prompt("Novo nome do webhook:");
    const newUrl = prompt("Novo URL do webhook:");

    if (id && newName && newUrl) {
        fetch('/edit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `type=webhook&id=${id}&name=${newName}&url=${newUrl}`
        }).then(response => response.json()).then(data => alert(data.message));
    }
}

function deleteWebhook() {
    const id = document.getElementById('webhook-list').value;
    if (id && confirm("Deseja realmente excluir este webhook?")) {
        fetch('/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `type=webhook&id=${id}`
        }).then(response => response.json()).then(data => alert(data.message));
    }
}
