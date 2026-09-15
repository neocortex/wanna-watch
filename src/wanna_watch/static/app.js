/* Browse a real catalog; all personal state is persisted by the local server. */
const $ = (selector) => document.querySelector(selector);
let currentStatus;
let providers = [];
let view = 'unseen';
let shown = 0;
let undoAction;
let toastTimer;
let loading = false;
let movieRequest = 0;
let statusRequest = 0;
let pendingPreferences = 0;
let preferenceQueue = Promise.resolve();
let filterTimer;
let filterRevision = 0;
let filtersDirty = false;
const languageNames = new Intl.DisplayNames(['en'], { type: 'language' });

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { 'Content-Type': 'application/json' } });
  if (response.status === 401) {
    location.assign("/login");
    throw new Error("Your session ended. Please sign in again.");
  }
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check your selections.');
  return data;
}

function showError(error) {
  $('#error').textContent = error.message || String(error);
  $('#error').hidden = false;
}

function clearError() { $('#error').hidden = true; }

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function link(label, href, className) {
  const node = element('a', className, label);
  node.href = href;
  node.target = '_blank';
  node.rel = 'noopener noreferrer';
  return node;
}

/** Create a decorative icon without changing its control's accessible name. */
function icon(name) {
  const paths = {
    check: 'M5 12l4 4L19 6',
    star: 'm12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9z',
    hide: 'M3 3l18 18M10 5.2a10 10 0 0 1 11 6.8 17 17 0 0 1-3 4M6 6a17 17 0 0 0-3 6s3 7 9 7a10 10 0 0 0 4-.8M10 10a3 3 0 0 0 4 4',
    restore: 'M4 5v6h6M4 11a8 8 0 1 1 1 7',
    external: 'M6 18 18 6M6 6h12v12',
  };
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'icon');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', paths[name]);
  svg.append(path);
  return svg;
}

async function loadStatus() {
  const request = ++statusRequest;
  const s = await api('/api/status');
  if (request !== statusRequest) return;
  const previous = currentStatus;
  currentStatus = s;
  $('#refresh').disabled = s.running || !s.configured || !s.preferences.provider_ids.length;
  $('#refresh-label').textContent = s.running ? 'Refreshing…' : 'Refresh catalog';
  $('#refresh').classList.toggle('is-refreshing', s.running);
  $('#edit-services').disabled = s.running;
  $('#min-votes').disabled = s.running;
  $('#film-filters').disabled = s.running;
  if (!pendingPreferences && !filtersDirty && !filterTimer) {
    if (JSON.stringify(previous?.preferences) !== JSON.stringify(s.preferences)
        || JSON.stringify(previous?.genres) !== JSON.stringify(s.genres)) renderFilters();
    $('#min-votes').value = String(s.preferences.min_votes);
  }
  const notice = $('#notice');
  notice.className = 'notice';
  if (s.running) notice.textContent = s.message;
  else if (!s.configured) notice.textContent = 'Connect TMDB to load your German subscription catalog. See the README for setup.';
  else if (!s.preferences.provider_ids.length) notice.textContent = 'Choose your subscriptions, then refresh to find your titles.';
  else if (!s.snapshot) notice.textContent = 'Ready to build your first catalog. Refreshing may take several minutes.';
  else if (s.needs_refresh) {
    notice.classList.add('stale');
    notice.textContent = 'Refresh needed: this catalog is older than 24 hours or does not cover your selected services and title types.';
  } else {
    notice.classList.add('fresh');
    notice.textContent = `Updated ${new Date(s.snapshot.completed_at).toLocaleString()}`;
  }
  if (s.error) showError(new Error(s.error));
  $('#coverage').hidden = !s.snapshot;
  if (s.snapshot) {
    const c = s.snapshot;
    $('#coverage-text').textContent = `${c.discovered.toLocaleString()} titles discovered across ${c.provider_ids.length} subscriptions; ${c.ranked.toLocaleString()} matched to IMDb and a selected German subscription offer. ${c.without_imdb_rating.toLocaleString()} omitted without an IMDb rating; ${c.without_subscription_offer.toLocaleString()} omitted without a matching subscription offer. All discovery pages were collected before ranking. IMDb source updated: ${c.ratings_modified}. Availability collection started: ${new Date(c.started_at).toLocaleString()}.`;
  }
  renderSelected();
  if (previous?.running && !s.running) await loadMovies();
}

function renderSelected() {
  const container = $('#selected-services');
  container.replaceChildren();
  const ids = currentStatus.preferences.provider_ids;
  if (!ids.length) container.append(element('span', 'muted', 'Choose the subscriptions you pay for.'));
  for (const id of ids) {
    const provider = providers.find(p => p.provider_id === id);
    const chip = element('span', 'chip', provider?.provider_name || `Service ${id}`);
    chip.prepend(icon('check'));
    container.append(chip);
  }
}

function renderFilters() {
  const prefs = currentStatus.preferences;
  $('#media-type').value = prefs.media_type === 'tv' ? 'tv' : 'movie';
  renderMediaTabs();
  $('#language').value = prefs.language || 'all';
  renderYearOptions(prefs.after_year);
  $('#imdb-rating').value = prefs.imdb_rating ?? '';
  $('#genre-options').replaceChildren();
  const genres = [...(currentStatus.genres || []), { id: 'standup', name: 'Stand-up comedy' }]
    .sort((a, b) => a.name.localeCompare(b.name));
  for (const genre of genres) {
    const label = element('label', 'genre-option');
    const input = element('input');
    input.type = 'checkbox'; input.value = genre.id;
    if (genre.id === 'standup') input.id = 'exclude-standup';
    input.checked = genre.id === 'standup' ? prefs.exclude_standup : (prefs.excluded_genres || []).includes(genre.id);
    label.append(input, document.createTextNode(genre.name));
    $('#genre-options').append(label);
  }
  const hidden = (prefs.excluded_genres || []).length + Number(prefs.exclude_standup || false);
  $('#genre-summary').textContent = `Exclude genres${hidden ? ` · ${hidden} excluded` : ''}`;
}

/** Populate the exclusive release-year filter with complete, readable choices. */
function renderYearOptions(selectedYear) {
  const select = $('#after-year');
  const latestYear = new Date().getFullYear() - 1;
  const years = Array.from({ length: latestYear - 1899 }, (_, index) => latestYear - index);
  if (Number.isInteger(selectedYear) && !years.includes(selectedYear)) years.push(selectedYear);
  select.replaceChildren(new Option('Any year', ''));
  for (const year of years.sort((first, second) => second - first)) {
    select.append(new Option(String(year), String(year)));
  }
  select.value = selectedYear ?? '';
}

function renderMovie(movie, rank) {
  const card = element('article', 'movie-card');
  card.dataset.movieId = movie.id;
  card.dataset.mediaType = movie.media_type || 'movie';
  const poster = link('', `https://www.imdb.com/title/${movie.imdb_id}/`, 'poster-wrap');
  poster.setAttribute('aria-label', `${movie.title} on IMDb`);
  if (movie.poster_path && /^\/[a-zA-Z0-9._-]+$/.test(movie.poster_path)) {
    const img = element('img');
    img.src = `https://image.tmdb.org/t/p/w342${movie.poster_path}`;
    img.alt = `${movie.title} poster`;
    img.loading = 'lazy';
    img.addEventListener('error', () => img.replaceWith(element('div', 'poster-placeholder', movie.title)));
    poster.append(img);
  } else poster.append(element('div', 'poster-placeholder', movie.title));
  poster.append(element('span', 'rank', String(rank).padStart(2, '0')));
  card.append(poster, element('h2', 'movie-title', movie.title));
  const isSeries = movie.media_type === 'tv';
  const duration = isSeries
    ? (movie.number_of_seasons ? `${movie.number_of_seasons} season${movie.number_of_seasons === 1 ? '' : 's'}` : '')
    : (movie.runtime ? `${movie.runtime} min` : '');
  card.append(element('p', 'movie-meta', [isSeries ? 'Series' : 'Film', movie.year, duration].filter(Boolean).join(' · ')));
  const originalLanguage = movie.original_language
    ? languageNames.of(movie.original_language) : 'Unknown language';
  card.append(element('p', 'movie-language', originalLanguage));
  const genres = (movie.genres || []).map(genre => genre.name);
  if (movie.is_standup) genres.push('Stand-up comedy');
  card.append(element('p', 'movie-genres', genres.join(' · ') || 'Genres unavailable'));
  const rating = element('div', 'rating-line');
  const score = link(movie.imdb_rating.toFixed(1), `https://www.imdb.com/title/${movie.imdb_id}/`, 'rating');
  score.setAttribute('aria-label', `IMDb rating ${movie.imdb_rating.toFixed(1)}`);
  score.prepend(icon('star'));
  rating.append(score);
  rating.append(element('span', 'rating-label', `IMDb · ${movie.imdb_votes.toLocaleString()} votes`));
  const offers = element('p', 'providers');
  for (const provider of movie.providers) {
    const offer = element('span', 'provider-offer', provider.provider_name);
    offer.dataset.providerId = provider.provider_id;
    offers.append(offer);
  }
  card.append(rating, offers);
  const synopsis = element('details', 'synopsis');
  synopsis.append(element('summary', '', 'Synopsis'), element('p', '', movie.overview || 'No synopsis available.'));
  card.append(synopsis);
  const actions = element('div', 'movie-actions');
  const choices = view === 'unseen' ? [['watched', 'Watched'], ['hidden', 'Hide']] : [['unseen', 'Restore']];
  for (const [state, label] of choices) {
    const button = element('button', '', label);
    button.prepend(icon(state === 'watched' ? 'check' : state === 'hidden' ? 'hide' : 'restore'));
    button.addEventListener('click', () => changeState(movie, state, button));
    actions.append(button);
  }
  const watchLink = link('Where to watch', `https://www.themoviedb.org/${movie.media_type || 'movie'}/${movie.id}/watch?locale=DE`, 'where-link');
  watchLink.append(icon('external'));
  card.append(actions, watchLink);
  return card;
}

async function loadMovies(append = false) {
  if (filtersDirty || filterTimer) return;
  if (append && loading) return;
  loading = true;
  const request = ++movieRequest;
  const requestedView = view;
  try {
    const offset = append ? shown : 0;
    const data = await api(`/api/movies?view=${requestedView}&offset=${offset}&limit=40`);
    if (request !== movieRequest || requestedView !== view || filtersDirty || filterTimer) return;
    if (!append) { audioObserver.disconnect(); $('#movies').replaceChildren(); shown = 0; }
    for (const movie of data.movies) {
      const card = renderMovie(movie, ++shown);
      $('#movies').append(card);
      observeAudio(card, movie);
    }
    $('#count').textContent = `${data.total.toLocaleString()} titles`;
    $('#load-more').hidden = shown >= data.total;
    $('#empty').hidden = data.total > 0;
    $('#empty-text').textContent = !currentStatus?.snapshot
      ? 'Choose your subscriptions and refresh the catalog. Your titles will appear here, ranked by IMDb.'
      : view === 'unseen'
        ? 'No titles match this selection. Try resetting filters, lowering the vote threshold, changing services, or refreshing the catalog.'
        : `You haven’t marked any matching titles as ${view} yet.`;
  } finally { if (request === movieRequest) loading = false; }
}

async function changeState(movie, state, button) {
  button.disabled = true;
  try {
    const previousState = view;
    await api(`/api/titles/${movie.media_type || 'movie'}/${movie.id}/state`, { method: 'PUT', body: JSON.stringify({ state }) });
    undoAction = { id: movie.id, media_type: movie.media_type || 'movie', state: previousState };
    $('#toast-message').textContent = state === 'unseen' ? `${movie.title} restored` : `${movie.title} marked ${state}`;
    $('#toast').hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 10000);
    await loadMovies();
  } catch (error) { showError(error); } finally { button.disabled = false; }
}

$('#undo').addEventListener('click', async () => {
  if (!undoAction) return;
  try {
    await api(`/api/titles/${undoAction.media_type}/${undoAction.id}/state`, { method: 'PUT', body: JSON.stringify({ state: undoAction.state }) });
    $('#toast').hidden = true;
    undoAction = undefined;
    await loadMovies();
  } catch (error) { showError(error); }
});

$('#edit-services').addEventListener('click', async () => {
  $('#services-dialog').showModal();
  $('#provider-message').textContent = 'Loading German services…';
  $('#save-services').disabled = true;
  try {
    ({ providers } = await api('/api/providers'));
    $('#provider-options').replaceChildren();
    $('#provider-search').value = '';
    for (const provider of providers) {
      const label = element('label', 'provider-option');
      label.dataset.name = provider.provider_name.toLowerCase();
      const input = element('input');
      input.type = 'checkbox'; input.value = provider.provider_id;
      input.checked = currentStatus.preferences.provider_ids.includes(provider.provider_id);
      label.append(input, document.createTextNode(provider.provider_name));
      $('#provider-options').append(label);
    }
    $('#provider-message').textContent = '';
    $('#save-services').disabled = false;
    renderSelected();
  } catch (error) { $('#provider-message').textContent = error.message; }
});

$('#close-dialog').addEventListener('click', () => $('#services-dialog').close());
$('#provider-search').addEventListener('input', (event) => {
  const query = event.target.value.toLowerCase();
  document.querySelectorAll('.provider-option').forEach(node => { node.hidden = !node.dataset.name.includes(query); });
});

function savePreferences(changes) {
  clearError();
  const revision = filterRevision;
  statusRequest++;
  pendingPreferences++;
  // Serialize writes so a slow response cannot overwrite a more recent selection.
  const save = preferenceQueue.then(async () => {
    const preferences = { ...currentStatus.preferences, ...changes };
    currentStatus.preferences = await api('/api/preferences', {
      method: 'PUT', body: JSON.stringify(preferences),
    });
    if (revision === filterRevision) filtersDirty = false;
    if (pendingPreferences === 1 && !filterTimer) {
      await loadStatus();
      await loadMovies();
    }
  }).finally(() => { pendingPreferences--; });
  preferenceQueue = save.catch(() => {});
  return save;
}

function readFilters() {
  return {
    media_type: $('#media-type').value,
    excluded_genres: [...document.querySelectorAll('#genre-options input:checked:not(#exclude-standup)')].map(input => Number(input.value)),
    exclude_standup: $('#exclude-standup').checked,
    language: $('#language').value,
    after_year: $('#after-year').value === '' ? null : Number($('#after-year').value),
    imdb_rating: $('#imdb-rating').value === '' ? null : Number($('#imdb-rating').value),
  };
}

function filterEdited() {
  filtersDirty = true;
  filterRevision++;
  statusRequest++;
  movieRequest++;
  loading = false;
}

function applyFilters() {
  clearTimeout(filterTimer);
  filterTimer = undefined;
  if (!$('#filters-form').checkValidity()) return;
  const filters = readFilters();
  const hidden = filters.excluded_genres.length + Number(filters.exclude_standup);
  $('#genre-summary').textContent = `Exclude genres${hidden ? ` · ${hidden} excluded` : ''}`;
  savePreferences(filters).catch(showError);
}

function renderMediaTabs() {
  document.querySelectorAll('button[data-media-type]').forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.mediaType === $('#media-type').value));
  });
}

document.querySelectorAll('button[data-media-type]').forEach(button => button.addEventListener('click', () => {
  if ($('#media-type').value === button.dataset.mediaType) return;
  $('#media-type').value = button.dataset.mediaType;
  renderMediaTabs();
  filterEdited();
  applyFilters();
}));

$('#filters-form').addEventListener('input', event => {
  filterEdited();
  clearTimeout(filterTimer);
  filterTimer = undefined;
  if (event.target.type === 'number') filterTimer = setTimeout(applyFilters, 350);
  else applyFilters();
});
$('#filters-form').addEventListener('submit', event => {
  event.preventDefault();
  applyFilters();
});

$('#reset-filters').addEventListener('click', () => {
  clearTimeout(filterTimer);
  filterTimer = undefined;
  $('#language').value = 'en';
  $('#after-year').value = '';
  $('#imdb-rating').value = '';
  document.querySelectorAll('#genre-options input').forEach(input => {
    input.checked = input.id === 'exclude-standup' || ['16', '99'].includes(input.value);
  });
  filterEdited();
  applyFilters();
});

$('#services-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const ids = [...document.querySelectorAll('#provider-options input:checked')].map(input => Number(input.value));
  $('#save-services').disabled = true;
  try {
    await savePreferences({ provider_ids: ids });
    renderSelected();
    $('#services-dialog').close();
  } catch (error) { $('#provider-message').textContent = error.message; }
  finally { $('#save-services').disabled = false; }
});

$('#min-votes').addEventListener('change', async (event) => {
  filterEdited();
  try { await savePreferences({ min_votes: Number(event.target.value) }); }
  catch (error) { showError(error); await loadStatus(); }
});

$('#refresh').addEventListener('click', async () => {
  clearError();
  $('#refresh').disabled = true;
  try { await api('/api/refresh', { method: 'POST' }); await loadStatus(); }
  catch (error) { showError(error); $('#refresh').disabled = false; }
});

document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', async () => {
  if (loading) return;
  view = button.dataset.view;
  document.querySelectorAll('[data-view]').forEach(node => node.setAttribute('aria-pressed', String(node === button)));
  try { await loadMovies(); } catch (error) { showError(error); }
}));
$('#load-more').addEventListener('click', () => loadMovies(true).catch(showError));

async function start() {
  try {
    await loadStatus();
    if (currentStatus.configured || currentStatus.snapshot) {
      try { ({ providers } = await api('/api/providers')); renderSelected(); }
      catch (error) { showError(error); }
    }
    await loadMovies();
  } catch (error) { showError(error); }
  setInterval(() => { if (!pendingPreferences) loadStatus().catch(showError); }, 2000);
}
start();
