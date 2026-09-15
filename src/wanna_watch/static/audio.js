/* Fetch supplementary audio only for visible English-original cards. */
let audioQueue = Promise.resolve();
const audioObserver = new IntersectionObserver(entries => {
  for (const entry of entries) {
    if (!entry.isIntersecting) continue;
    const card = entry.target;
    audioObserver.unobserve(card);
    audioQueue = audioQueue.then(async () => {
      if (!card.isConnected) return;
      try {
        const data = await api(`/api/titles/${card.dataset.mediaType}/${card.dataset.movieId}/audio`);
        if (!card.isConnected) return;
        renderAudioWarnings(card, data.provider_ids);
      } catch {
        // Supplementary audio failures leave the catalog usable and unlabelled.
      }
    });
  }
}, { rootMargin: '400px 0px' });

function renderAudioWarnings(card, providerIds) {
  for (const id of providerIds) {
    const provider = card.querySelector(`[data-provider-id="${id}"]`);
    if (!provider || provider.querySelector('.audio-warning')) continue;
    const label = element('small', 'audio-warning', 'English may be unavailable');
    label.title = 'Reported subscription audio omits English. Check the service before playing; series may vary by episode.';
    provider.append(label);
  }
}

function observeAudio(card, movie) {
  if (movie.audio_warning_provider_ids != null) {
    renderAudioWarnings(card, movie.audio_warning_provider_ids);
    return;
  }
  if (movie.original_language === 'en' && movie.providers.some(p => [8, 9, 337].includes(p.provider_id))) {
    audioObserver.observe(card);
  }
}
