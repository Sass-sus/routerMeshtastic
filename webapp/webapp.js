const socket = io();
let currentNodeId = null;
let nodesById = {};

const nodeListEl = document.getElementById('node-list');
const messagesEl = document.getElementById('messages');
const chatHeaderEl = document.getElementById('chat-header');
const chatNameEl = document.getElementById('chat-name');
const chatIdEl = document.getElementById('chat-id');
const composerEl = document.getElementById('composer');
const inputEl = document.getElementById('msg-input');
const sendBtn = document.getElementById('send-btn');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');

function initials(name){
  if(!name) return '?';
  const parts = name.trim().split(/\s+/);
  if(parts.length === 1) return parts[0].slice(0,2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function formatTime(iso){
  if(!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString('fr-FR', {day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit'});
}

function renderNodeList(nodes){
  nodesById = {};
  nodeListEl.innerHTML = '';
  nodes.forEach(n => {
    nodesById[n.id] = n;
    const item = document.createElement('div');
    item.className = 'node-item' + (n.id === currentNodeId ? ' active' : '');
    item.dataset.id = n.id;
    item.innerHTML = `
      <div class="avatar">${n.id === 'broadcast' ? 'ALL' : initials(n.name)}</div>
      <div class="meta">
        <div class="name">${n.name}</div>
        <div class="preview">${n.lastMessage ? n.lastMessage : (n.id === 'broadcast' ? 'Canal commun du réseau' : 'Aucun message')}</div>
      </div>
    `;
    item.addEventListener('click', () => selectNode(n.id));
    nodeListEl.appendChild(item);
  });
}

async function loadNodes(){
  const res = await fetch('/api/nodes');
  const nodes = await res.json();
  renderNodeList(nodes);
}

async function selectNode(nodeId){
  currentNodeId = nodeId;
  document.querySelectorAll('.node-item').forEach(el => {
    el.classList.toggle('active', el.dataset.id === nodeId);
  });

  const node = nodesById[nodeId];
  chatHeaderEl.style.display = 'flex';
  composerEl.style.display = 'flex';
  chatNameEl.textContent = node ? node.name : nodeId;
  chatIdEl.textContent = nodeId === 'broadcast' ? '' : nodeId;

  const res = await fetch('/api/messages/' + encodeURIComponent(nodeId));
  const msgs = await res.json();
  renderMessages(msgs);
  inputEl.focus();
}

function renderMessages(msgs){
  messagesEl.innerHTML = '';
  if(msgs.length === 0){
    messagesEl.innerHTML = '<div class="empty-state">Aucun message pour le moment.<br>Écrivez ci-dessous pour démarrer l’échange.</div>';
    return;
  }
  msgs.forEach(m => appendMessage(m, false));
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function appendMessage(m, scroll=true){
  if(messagesEl.querySelector('.empty-state')) messagesEl.innerHTML = '';
  const div = document.createElement('div');
  div.className = 'msg ' + (m.direction === 'out' ? 'out' : 'in');
  div.innerHTML = `${escapeHtml(m.text)}<span class="ts mono">${m.direction === 'out' ? 'vous' : (m.node_name || '')} · ${formatTime(m.timestamp)}</span>`;
  messagesEl.appendChild(div);
  if(scroll) messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(str){
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

async function sendMessage(){
  const text = inputEl.value.trim();
  if(!text || !currentNodeId) return;
  inputEl.value = '';
  sendBtn.disabled = true;
  try{
    const res = await fetch('/api/send', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({node_id: currentNodeId, text})
    });
    const data = await res.json();
    if(data.error){
      alert('Erreur : ' + data.error);
    }
  } finally {
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

sendBtn.addEventListener('click', sendMessage);
inputEl.addEventListener('keydown', e => { if(e.key === 'Enter') sendMessage(); });

socket.on('new_message', (m) => {
  if(m.node_id === currentNodeId){
    appendMessage(m);
  }
  loadNodes();
});

socket.on('nodes_update', (nodes) => {
  renderNodeList(nodes);
});

socket.on('connection_status', (status) => {
  statusDot.classList.toggle('on', status.connected);
  statusText.textContent = status.detail;
});

fetch('/api/status').then(r => r.json()).then(status => {
  statusDot.classList.toggle('on', status.connected);
  statusText.textContent = status.detail;
});

loadNodes();
setInterval(loadNodes, 15000);