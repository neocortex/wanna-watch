/* Draft filter panels and persistent catalog browsing controls. */

/** Keep browsing controls unavailable while catalog settings are locked. */
function updateFilterControls() {
  for (const button of document.querySelectorAll('[data-media-type], #open-filters, #reset-filters')) {
    button.disabled = currentStatus.running;
  }
}

/** Build the service draft from saved subscriptions, keeping an empty subset explicit. */
function renderServiceOptions(p = currentStatus.preferences) {
  const container = $('#service-filter-options');
  container.replaceChildren();
  if (!p.provider_ids.length) container.append(element('p', 'muted', 'Add your subscriptions to start browsing.'));
  for (const id of p.provider_ids) {
    const label = element('label', 'provider-option');
    const input = element('input');
    input.type = 'checkbox';
    input.value = id;
    input.checked = p.service_ids === null || p.service_ids.includes(id);
    label.append(input, document.createTextNode(providers.find(p => p.provider_id === id)?.provider_name || `Service ${id}`));
    container.append(label);
  }
}

for (const button of document.querySelectorAll('[data-close]')) {
  button.addEventListener('click', () => document.getElementById(button.dataset.close).close());
}
$('#open-filters').addEventListener('click', () => {
  renderFilters();
  renderServiceOptions();
  $('#min-votes').value = currentStatus.preferences.min_votes;
  $('#filter-error').hidden = true;
  $('#filters-dialog').showModal();
});
$('#all-services').addEventListener('click', () => {
  document.querySelectorAll('#service-filter-options input').forEach(input => { input.checked = true; });
});
$('#clear-genres').addEventListener('click', () => {
  document.querySelectorAll('#genre-options input').forEach(input => { input.checked = false; });
});

/** Save the combined draft, retaining inputs and local feedback on failure. */
$('#filters-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = event.submitter;
  const ids = [...document.querySelectorAll('#service-filter-options input:checked')].map(input => Number(input.value));
  button.disabled = true;
  try {
    await savePreferences({ ...readFilters(),
      service_ids: ids.length === currentStatus.preferences.provider_ids.length ? null : ids });
    $('#filters-dialog').close();
  } catch (error) {
    $('#filter-error').textContent = error.message;
    $('#filter-error').hidden = false;
  } finally { button.disabled = false; }
});
$('#reset-filters').addEventListener('click', () => {
  const defaults = { ...currentStatus.preferences, service_ids: null, min_votes: 5000, language: 'en',
    after_year: null, imdb_rating: null, excluded_genres: [16, 99], exclude_standup: true };
  renderFilters(defaults);
  renderServiceOptions(defaults);
  $('#min-votes').value = defaults.min_votes;
  $('#filter-error').hidden = true;
});
start();
