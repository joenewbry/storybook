/**
 * API client for Storybook backend.
 */
const API = {
    async _fetch(url, opts = {}) {
        const res = await fetch(url, {
            headers: { 'Content-Type': 'application/json', ...opts.headers },
            ...opts,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || 'Request failed');
        }
        return res.json();
    },

    // Stories
    listStories() { return this._fetch('/api/stories'); },
    createStory(data) { return this._fetch('/api/stories', { method: 'POST', body: JSON.stringify(data) }); },
    getStory(id) { return this._fetch(`/api/stories/${id}`); },
    getStoryFull(id) { return this._fetch(`/api/stories/${id}/full`); },
    updateStory(id, data) { return this._fetch(`/api/stories/${id}`, { method: 'PATCH', body: JSON.stringify(data) }); },
    deleteStory(id) { return this._fetch(`/api/stories/${id}`, { method: 'DELETE' }); },

    // Segmentation
    segmentStory(id) { return this._fetch(`/api/stories/${id}/segment`, { method: 'POST' }); },

    // Shot breakdown
    breakdownScene(sceneId) { return this._fetch(`/api/scenes/${sceneId}/breakdown`, { method: 'POST' }); },
    breakdownAll(storyId) { return this._fetch(`/api/stories/${storyId}/breakdown-all`, { method: 'POST' }); },

    // Shots
    getShot(id) { return this._fetch(`/api/shots/${id}`); },
    updateShot(id, data) { return this._fetch(`/api/shots/${id}`, { method: 'PATCH', body: JSON.stringify(data) }); },
    reorderShots(shotIds) { return this._fetch('/api/shots/reorder', { method: 'POST', body: JSON.stringify({ shot_ids: shotIds }) }); },

    // Generation
    generateShot(shotId) { return this._fetch(`/api/shots/${shotId}/generate`, { method: 'POST' }); },
    generateAll(storyId) { return this._fetch(`/api/stories/${storyId}/generate-all`, { method: 'POST' }); },
    buildPrompts(storyId) { return this._fetch(`/api/stories/${storyId}/build-prompts`, { method: 'POST' }); },

    // Composition
    composeScene(sceneId) { return this._fetch(`/api/scenes/${sceneId}/compose`, { method: 'POST' }); },
};
