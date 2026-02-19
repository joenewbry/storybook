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

    // World Bible
    extractWorldBible(storyId) { return this._fetch(`/api/stories/${storyId}/world-bible/extract`, { method: 'POST' }); },
    getWorldBible(storyId) { return this._fetch(`/api/stories/${storyId}/world-bible`); },
    generateAllReferences(storyId) { return this._fetch(`/api/stories/${storyId}/world-bible/generate-all-references`, { method: 'POST' }); },

    // Characters
    updateCharacter(id, data) { return this._fetch(`/api/characters/${id}`, { method: 'PATCH', body: JSON.stringify(data) }); },
    deleteCharacter(id) { return this._fetch(`/api/characters/${id}`, { method: 'DELETE' }); },
    generateCharRefs(id) { return this._fetch(`/api/characters/${id}/generate-references`, { method: 'POST' }); },

    // Locations
    updateLocation(id, data) { return this._fetch(`/api/locations/${id}`, { method: 'PATCH', body: JSON.stringify(data) }); },
    deleteLocation(id) { return this._fetch(`/api/locations/${id}`, { method: 'DELETE' }); },
    generateLocRefs(id) { return this._fetch(`/api/locations/${id}/generate-references`, { method: 'POST' }); },

    // Props
    updateProp(id, data) { return this._fetch(`/api/props/${id}`, { method: 'PATCH', body: JSON.stringify(data) }); },
    deleteProp(id) { return this._fetch(`/api/props/${id}`, { method: 'DELETE' }); },
    generatePropRefs(id) { return this._fetch(`/api/props/${id}/generate-references`, { method: 'POST' }); },

    // Camera Bible
    updateCameraBible(id, data) { return this._fetch(`/api/camera-bible/${id}`, { method: 'PATCH', body: JSON.stringify(data) }); },

    // Reference Approval
    approveCharRef(refId) { return this._fetch(`/api/character-references/${refId}/approve`, { method: 'POST' }); },
    approveLocRef(refId) { return this._fetch(`/api/location-references/${refId}/approve`, { method: 'POST' }); },
    approvePropRef(refId) { return this._fetch(`/api/prop-references/${refId}/approve`, { method: 'POST' }); },
};
