// Фронт помогатора: доска chessground + панель с подсказками.
import { Chessground } from 'chessground';

const BRUSHES = ['green', 'blue', 'yellow'];
const STATUS_TEXT = { check: 'Шах!', checkmate: 'Мат', stalemate: 'Пат', draw: 'Ничья' };
const GAME_OVER = ['checkmate', 'stalemate', 'draw'];

const el = (id) => document.getElementById(id);
const api = () => window.pywebview.api;
let state = null;
let moveInFlight = false; // идёт запрос хода к бэку: поздний анализ старой позиции игнорируем

const cg = Chessground(el('board'), {
  premovable: { enabled: false },
  movable: { free: false, showDests: true, events: { after: onUserMove } },
  highlight: { lastMove: true, check: true },
  animation: { enabled: true, duration: 150 },
});

// Общий вызов бэка: рендерит ответ; при ошибке показывает её и пересинхронизирует доску
async function call(fn) {
  try {
    render(await fn());
  } catch (err) {
    const message = String(err?.message ?? err);
    showError(el('action-error'), message);
    try {
      render(await api().get_state());
      showError(el('action-error'), message); // render мог стереть текст ошибки
    } catch {
      // состояние не получить — оставляем сообщение об ошибке
    }
  }
}

async function onUserMove(orig, dest) {
  clearHints(); // старые стрелки больше не актуальны
  moveInFlight = true;
  try {
    await call(() => api().move(orig, dest));
  } finally {
    moveInFlight = false;
  }
}

function render(next) {
  // подсказки сбрасываем, только если позиция действительно сменилась
  const changed = !state || next.fen !== state.fen || next.my_color !== state.my_color;
  state = next;
  cg.set({
    fen: state.fen,
    orientation: state.my_color,
    turnColor: state.turn,
    lastMove: state.last_move ?? undefined,
    check: state.status === 'check' || state.status === 'checkmate',
    movable: { color: state.turn, dests: new Map(Object.entries(state.dests)) },
  });
  if (changed) clearHints(); // свежие подсказки придут в onAnalysis
  renderStatus();
}

function clearHints() {
  cg.setAutoShapes([]);
  el('lines').innerHTML = '';
  el('depth').textContent = '';
}

function renderStatus() {
  const turn = state.turn === state.my_color ? 'Твой ход' : 'Ход соперника — повтори его';
  const extra = STATUS_TEXT[state.status];
  if (GAME_OVER.includes(state.status)) {
    el('status').textContent = `Игра окончена: ${extra}`;
  } else {
    el('status').textContent = extra ? `${turn} · ${extra}` : turn;
  }
  showError(el('engine-error'), state.engine_error);
  showError(el('action-error'), state.error);
  el('history').textContent = formatHistory(state.history);
}

function showError(node, text) {
  node.hidden = !text;
  node.textContent = text ?? '';
}

function formatHistory(sans) {
  const parts = [];
  for (let i = 0; i < sans.length; i += 2) {
    parts.push(`${i / 2 + 1}. ${sans[i]}${sans[i + 1] ? ' ' + sans[i + 1] : ''}`);
  }
  return parts.join('  ');
}

function formatScore({ cp, mate }) {
  if (mate !== null) return mate > 0 ? `мат в ${mate}` : `тебе мат в ${-mate}`;
  const pawns = cp / 100;
  return `${pawns > 0 ? '+' : ''}${pawns.toFixed(1)}`;
}

// Бэк вызывает эту функцию через evaluate_js по мере расчёта
window.onAnalysis = (result) => {
  if (moveInFlight || !state || result.fen !== state.fen || state.turn !== state.my_color) return; // устаревший анализ
  const shapes = result.lines.map((line, i) => ({
    orig: line.uci.slice(0, 2),
    dest: line.uci.slice(2, 4),
    brush: BRUSHES[i],
  }));
  cg.setAutoShapes(shapes.reverse()); // зелёная стрелка рисуется последней, поверх остальных
  el('lines').innerHTML = '';
  result.lines.forEach((line, i) => {
    const li = document.createElement('li');
    li.className = `line-${BRUSHES[i]}`;
    li.textContent = `${line.san}  ${formatScore(line.score)}`;
    el('lines').appendChild(li);
  });
  el('depth').textContent = `Глубина ${result.depth}`;
};

el('new-white').addEventListener('click', () => call(() => api().new_game('white')));
el('new-black').addEventListener('click', () => call(() => api().new_game('black')));
el('undo').addEventListener('click', () => call(() => api().undo()));
el('on-top').addEventListener('change', (e) => call(() => api().set_on_top(e.target.checked)));
el('load-fen').addEventListener('click', () => call(() => api().load_fen(el('fen-input').value.trim())));

document.addEventListener('keydown', (e) => {
  // в текстовом поле Ctrl+Z — это отмена ввода, а не отмена хода; чекбокс не в счёт
  if (e.target?.matches?.('textarea, input:not([type="checkbox"])')) return;
  // KeyZ не зависит от раскладки (работает и на русской)
  if (e.ctrlKey && e.code === 'KeyZ') {
    e.preventDefault();
    call(() => api().undo());
  }
});

function start() {
  return call(() => api().new_game('white'));
}

if (window.pywebview?.api) start();
else window.addEventListener('pywebviewready', start, { once: true });
