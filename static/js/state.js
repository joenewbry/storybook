/**
 * Simple reactive state manager.
 */
const State = {
    _data: {
        stories: [],
        currentStory: null,     // full story with chapters/scenes/shots
        selectedScene: null,    // scene id
        selectedShot: null,     // shot id
        view: 'create',         // 'create' | 'timeline'
        loading: false,
    },
    _listeners: [],

    get(key) { return this._data[key]; },

    set(key, value) {
        this._data[key] = value;
        this._notify(key);
    },

    onChange(fn) {
        this._listeners.push(fn);
    },

    _notify(key) {
        for (const fn of this._listeners) {
            try { fn(key, this._data[key]); } catch(e) { console.error('State listener error:', e); }
        }
    },
};
