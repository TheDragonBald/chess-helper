// Фронт помогатора: доска chessground + панель с подсказками.
import { Chessground } from 'chessground';

const BRUSHES = ['green', 'blue', 'yellow'];
const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
const GAME_OVER_TEXT = { checkmate: 'Мат', stalemate: 'Пат', draw: 'Ничья' };
const DRAW_REASON_TEXT = {
  insufficient_material: 'мало фигур для мата',
  fivefold_repetition: 'пятикратное повторение',
  seventyfive_moves: '75 ходов без взятий и ходов пешек',
};
const CLAIM_TEXT = {
  threefold_repetition: 'троекратное повторение',
  fifty_moves: '50 ходов без взятий и ходов пешек',
};
const CONFIRM_MS = 3000; // столько ждём второго нажатия «Новая за…»

const el = (id) => document.getElementById(id);
const api = () => window.pywebview.api;
let state = null;
let pendingAnalysis = null; // анализ позиции, чьё состояние ещё не дошло до фронта

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

function onUserMove(orig, dest) {
  // старые стрелки сотрёт render, когда придёт новая позиция
  return call(() => api().move(orig, dest));
}

function render(next) {
  // Ответы бэка приходят из разных потоков и могут обогнать друг друга:
  // состояние со старым номером версии уже неактуально
  if (state && next.rev < state.rev) return;
  const changed = !state || next.rev !== state.rev;
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
  // Анализ этой позиции мог прийти раньше её состояния
  if (pendingAnalysis && pendingAnalysis.rev <= state.rev) {
    const result = pendingAnalysis;
    pendingAnalysis = null;
    if (result.rev === state.rev) showAnalysis(result);
  }
}

function clearHints() {
  cg.setAutoShapes([]);
  el('lines').innerHTML = '';
  el('depth').textContent = '';
}

function statusText() {
  const over = GAME_OVER_TEXT[state.status];
  if (over) {
    const reason = DRAW_REASON_TEXT[state.draw_reason];
    return `Игра окончена: ${over}${reason ? ` (${reason})` : ''}`;
  }
  const parts = [state.turn === state.my_color ? 'Твой ход' : 'Ход соперника — повтори его'];
  if (state.status === 'check') parts.push('Шах!');
  const claim = CLAIM_TEXT[state.claimable_draw];
  if (claim) parts.push(`можно потребовать ничью: ${claim}`);
  return parts.join(' · ');
}

function renderStatus() {
  el('status').textContent = statusText();
  showError(el('engine-error'), state.engine_error);
  showError(el('action-error'), state.error);
  el('history').textContent = formatHistory(state.history, state.history_start);
}

function showError(node, text) {
  node.hidden = !text;
  node.textContent = text ?? '';
}

function formatHistory(sans, start) {
  // После FEN с ходом чёрных первая запись выглядит как «12... e5»
  const parts = [];
  let number = start.number;
  let i = 0;
  if (start.turn === 'black' && sans.length > 0) {
    parts.push(`${number}... ${sans[0]}`);
    number += 1;
    i = 1;
  }
  for (; i < sans.length; i += 2, number += 1) {
    parts.push(`${number}. ${sans[i]}${sans[i + 1] ? ' ' + sans[i + 1] : ''}`);
  }
  return parts.join('  ');
}

function formatScore({ cp, mate }) {
  if (mate !== null) return mate > 0 ? `мат в ${mate}` : `тебе мат в ${-mate}`;
  const pawns = cp / 100;
  if (Math.abs(pawns) < 0.05) return '0.0'; // иначе −0.03 показалось бы как «-0.0»
  return `${pawns > 0 ? '+' : ''}${pawns.toFixed(1)}`;
}

function showAnalysis(result) {
  if (state.turn !== state.my_color) return; // на ходу соперника подсказки не нужны
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
}

// Бэк вызывает эту функцию через evaluate_js по мере расчёта
window.onAnalysis = (result) => {
  if (state && result.rev < state.rev) return; // анализ старой позиции
  if (!state || result.rev > state.rev) {
    // ответ на действие ещё в пути — покажем анализ, когда придёт состояние
    if (!pendingAnalysis || result.rev >= pendingAnalysis.rev) pendingAnalysis = result;
    return;
  }
  showAnalysis(result);
};

// Бэк сообщает о падении движка сразу, не дожидаясь следующего действия
window.onEngineError = (message) => {
  clearHints();
  showError(el('engine-error'), message);
};

// «Новая за…» стирает партию: если терять есть что, просим нажать второй раз
function confirmNewGame(button, color) {
  const hasGame = state && (state.history.length > 0 || state.fen !== START_FEN);
  if (hasGame && !button.dataset.label) {
    button.dataset.label = button.textContent;
    button.textContent = 'Точно? Нажми ещё раз';
    setTimeout(() => resetConfirm(button), CONFIRM_MS);
    return;
  }
  resetConfirm(button);
  call(() => api().new_game(color));
}

function resetConfirm(button) {
  if (button.dataset.label) {
    button.textContent = button.dataset.label;
    delete button.dataset.label;
  }
}

const loadFen = () => call(() => api().load_fen(el('fen-input').value.trim()));

el('new-white').addEventListener('click', (e) => confirmNewGame(e.currentTarget, 'white'));
el('new-black').addEventListener('click', (e) => confirmNewGame(e.currentTarget, 'black'));
el('undo').addEventListener('click', () => call(() => api().undo()));
el('on-top').addEventListener('change', (e) => call(() => api().set_on_top(e.target.checked)));
el('load-fen').addEventListener('click', loadFen);
el('fen-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') loadFen();
});

document.addEventListener('keydown', (e) => {
  // в текстовом поле Ctrl+Z — это отмена ввода, а не отмена хода; чекбокс не в счёт
  if (e.target?.matches?.('textarea, input:not([type="checkbox"])')) return;
  // KeyZ не зависит от раскладки; Shift/Alt — другие сочетания; автоповтор не отменяет пачку ходов
  if (e.ctrlKey && !e.shiftKey && !e.altKey && !e.metaKey && e.code === 'KeyZ') {
    e.preventDefault();
    if (!e.repeat) call(() => api().undo());
  }
});

function start() {
  return call(() => api().new_game('white'));
}

if (window.pywebview?.api) start();
else window.addEventListener('pywebviewready', start, { once: true });
