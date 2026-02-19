/**
 * World Bible UI — Characters, Locations, Props, Camera tabs
 */

const WorldBibleUI = {
    init() {
        // Tab clicks
        document.querySelectorAll('.wb-tab').forEach(tab => {
            tab.onclick = () => {
                State.set('wbTab', tab.dataset.tab);
                State.set('selectedEntity', null);
                this.render();
            };
        });
    },

    async loadWorldBible(storyId) {
        try {
            const wb = await API.getWorldBible(storyId);
            State.set('worldBible', wb);
            this.render();
        } catch(e) {
            // No world bible yet — show empty state
            State.set('worldBible', null);
            this.render();
        }
    },

    render() {
        const wb = State.get('worldBible');
        const emptyEl = document.getElementById('wb-empty');
        const contentEl = document.getElementById('wb-content');

        if (!wb) {
            emptyEl.style.display = '';
            contentEl.style.display = 'none';
            return;
        }

        emptyEl.style.display = 'none';
        contentEl.style.display = '';

        // Update active tab
        const tab = State.get('wbTab');
        document.querySelectorAll('.wb-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.tab === tab);
        });

        this.renderList(wb, tab);
        this.renderDetail(wb, tab);
    },

    renderList(wb, tab) {
        const el = document.getElementById('wb-list');
        const selected = State.get('selectedEntity');

        if (tab === 'camera') {
            // Camera bible has no list — just show detail
            el.innerHTML = `<div class="wb-camera-summary">
                <h4>Camera & Film Look</h4>
                <p style="color:var(--text-dim);font-size:12px;">Edit the camera bible to control the visual feel of all generated images.</p>
                <button class="btn btn-secondary btn-sm" onclick="WorldBibleUI.selectCamera()">Edit Camera Bible</button>
            </div>`;
            return;
        }

        const entities = tab === 'characters' ? wb.characters :
                         tab === 'locations' ? wb.locations :
                         wb.props;

        if (!entities || entities.length === 0) {
            el.innerHTML = `<div style="padding:20px;color:var(--text-dim);font-size:13px;">No ${tab} found. Try re-extracting the world bible.</div>`;
            return;
        }

        el.innerHTML = entities.map(e => {
            const isSelected = selected && selected.type === tab.slice(0, -1) && selected.id === e.id;
            const thumbRef = e.approved_ref && e.approved_ref.file_path;
            const thumbSrc = thumbRef ? `/generated/${thumbRef}` : '';
            const refCount = (e.references || []).length;
            const subtitle = tab === 'characters' ? (e.role || '') :
                            tab === 'locations' ? (e.location_type || '') :
                            (e.category || '');

            return `<div class="wb-entity-card ${isSelected ? 'selected' : ''}" data-type="${tab.slice(0,-1)}" data-id="${e.id}">
                <div class="wb-entity-thumb">
                    ${thumbSrc ? `<img src="${thumbSrc}" alt="${_esc(e.name)}">` : '<div class="wb-thumb-placeholder">?</div>'}
                </div>
                <div class="wb-entity-info">
                    <div class="wb-entity-name">${_esc(e.name)}</div>
                    <div class="wb-entity-subtitle">${_esc(subtitle)}</div>
                    <div class="wb-entity-refs">${refCount} ref${refCount !== 1 ? 's' : ''}</div>
                </div>
            </div>`;
        }).join('');

        el.querySelectorAll('.wb-entity-card').forEach(card => {
            card.onclick = () => {
                State.set('selectedEntity', {
                    type: card.dataset.type,
                    id: parseInt(card.dataset.id),
                });
                this.render();
            };
        });
    },

    renderDetail(wb, tab) {
        const el = document.getElementById('wb-detail');
        const selected = State.get('selectedEntity');

        if (tab === 'camera') {
            this.renderCameraDetail(el, wb);
            return;
        }

        if (!selected) {
            el.innerHTML = '<div class="empty-state"><p>Select an entity to view details</p></div>';
            return;
        }

        const entities = tab === 'characters' ? wb.characters :
                         tab === 'locations' ? wb.locations :
                         wb.props;
        const entity = entities.find(e => e.id === selected.id);
        if (!entity) {
            el.innerHTML = '<div class="empty-state"><p>Entity not found</p></div>';
            return;
        }

        if (selected.type === 'character') this.renderCharDetail(el, entity);
        else if (selected.type === 'location') this.renderLocDetail(el, entity);
        else if (selected.type === 'prop') this.renderPropDetail(el, entity);
    },

    renderCharDetail(el, char) {
        el.innerHTML = `
        <div class="wb-detail-scroll">
            <h3>${_esc(char.name)}</h3>
            <div class="wb-detail-grid">
                <div class="detail-field"><label>Role</label><input data-field="role" value="${_esc(char.role)}"></div>
                <div class="detail-field"><label>Age Appearance</label><input data-field="age_appearance" value="${_esc(char.age_appearance)}"></div>
                <div class="detail-field"><label>Gender Presentation</label><input data-field="gender_presentation" value="${_esc(char.gender_presentation)}"></div>
                <div class="detail-field"><label>Body Type</label><input data-field="body_type" value="${_esc(char.body_type)}"></div>
            </div>
            <div class="detail-field"><label>Face Description</label><textarea data-field="face_description" rows="2">${_esc(char.face_description)}</textarea></div>
            <div class="wb-detail-grid">
                <div class="detail-field"><label>Hair</label><input data-field="hair" value="${_esc(char.hair)}"></div>
                <div class="detail-field"><label>Skin</label><input data-field="skin" value="${_esc(char.skin)}"></div>
            </div>
            <div class="detail-field"><label>Clothing</label><textarea data-field="clothing_default" rows="1">${_esc(char.clothing_default)}</textarea></div>
            <div class="detail-field"><label>Distinctive Features</label><textarea data-field="distinctive_features" rows="1">${_esc(char.distinctive_features)}</textarea></div>
            <div class="detail-field"><label>Demeanor</label><input data-field="demeanor" value="${_esc(char.demeanor)}"></div>
            <div class="detail-field">
                <label>Prompt Description (injected into every image)</label>
                <textarea data-field="prompt_description" rows="4" class="prompt-preview">${_esc(char.prompt_description)}</textarea>
            </div>
            <div class="btn-group" style="margin-top:8px;">
                <button class="btn btn-secondary btn-sm" onclick="WorldBibleUI.saveEntity('character', ${char.id})">Save Changes</button>
                <button class="btn btn-primary btn-sm" onclick="WorldBibleUI.generateRefs('character', ${char.id})">Generate References</button>
            </div>
            <h4 style="margin-top:16px;">Reference Images</h4>
            <div class="wb-ref-gallery">${this._renderRefGallery(char.references || [], 'character')}</div>
        </div>`;

        el.querySelectorAll('[data-field]').forEach(input => {
            input.onblur = () => this.saveEntity('character', char.id);
        });
    },

    renderLocDetail(el, loc) {
        el.innerHTML = `
        <div class="wb-detail-scroll">
            <h3>${_esc(loc.name)}</h3>
            <div class="wb-detail-grid">
                <div class="detail-field"><label>Type</label><input data-field="location_type" value="${_esc(loc.location_type)}"></div>
                <div class="detail-field"><label>Time of Day</label><input data-field="time_of_day" value="${_esc(loc.time_of_day)}"></div>
            </div>
            <div class="detail-field"><label>Description</label><textarea data-field="description" rows="2">${_esc(loc.description)}</textarea></div>
            <div class="detail-field"><label>Architectural Style</label><input data-field="architectural_style" value="${_esc(loc.architectural_style)}"></div>
            <div class="detail-field"><label>Default Lighting</label><input data-field="lighting_default" value="${_esc(loc.lighting_default)}"></div>
            <div class="detail-field"><label>Atmosphere</label><input data-field="atmosphere" value="${_esc(loc.atmosphere)}"></div>
            <div class="detail-field"><label>Key Objects</label><textarea data-field="key_objects" rows="1">${_esc(loc.key_objects)}</textarea></div>
            <div class="detail-field">
                <label>Prompt Description (injected into every image)</label>
                <textarea data-field="prompt_description" rows="4" class="prompt-preview">${_esc(loc.prompt_description)}</textarea>
            </div>
            <div class="btn-group" style="margin-top:8px;">
                <button class="btn btn-secondary btn-sm" onclick="WorldBibleUI.saveEntity('location', ${loc.id})">Save Changes</button>
                <button class="btn btn-primary btn-sm" onclick="WorldBibleUI.generateRefs('location', ${loc.id})">Generate References</button>
            </div>
            <h4 style="margin-top:16px;">Reference Images</h4>
            <div class="wb-ref-gallery">${this._renderRefGallery(loc.references || [], 'location')}</div>
        </div>`;

        el.querySelectorAll('[data-field]').forEach(input => {
            input.onblur = () => this.saveEntity('location', loc.id);
        });
    },

    renderPropDetail(el, prop) {
        el.innerHTML = `
        <div class="wb-detail-scroll">
            <h3>${_esc(prop.name)}</h3>
            <div class="wb-detail-grid">
                <div class="detail-field"><label>Category</label><input data-field="category" value="${_esc(prop.category)}"></div>
                <div class="detail-field"><label>Scale</label><input data-field="scale" value="${_esc(prop.scale)}"></div>
            </div>
            <div class="detail-field"><label>Description</label><textarea data-field="description" rows="2">${_esc(prop.description)}</textarea></div>
            <div class="detail-field"><label>Visual Details</label><textarea data-field="visual_details" rows="2">${_esc(prop.visual_details)}</textarea></div>
            <div class="detail-field"><label>Material Notes</label><input data-field="material_notes" value="${_esc(prop.material_notes)}"></div>
            <div class="detail-field">
                <label>Prompt Description (injected into every image)</label>
                <textarea data-field="prompt_description" rows="4" class="prompt-preview">${_esc(prop.prompt_description)}</textarea>
            </div>
            <div class="btn-group" style="margin-top:8px;">
                <button class="btn btn-secondary btn-sm" onclick="WorldBibleUI.saveEntity('prop', ${prop.id})">Save Changes</button>
                <button class="btn btn-primary btn-sm" onclick="WorldBibleUI.generateRefs('prop', ${prop.id})">Generate References</button>
            </div>
            <h4 style="margin-top:16px;">Reference Images</h4>
            <div class="wb-ref-gallery">${this._renderRefGallery(prop.references || [], 'prop')}</div>
        </div>`;

        el.querySelectorAll('[data-field]').forEach(input => {
            input.onblur = () => this.saveEntity('prop', prop.id);
        });
    },

    renderCameraDetail(el, wb) {
        const cam = wb.camera_bible;
        if (!cam) {
            el.innerHTML = '<div class="empty-state"><p>No camera bible. Re-extract the world bible.</p></div>';
            return;
        }

        el.innerHTML = `
        <div class="wb-detail-scroll">
            <h3>Camera Bible</h3>
            <p style="color:var(--text-dim);font-size:12px;margin-bottom:12px;">These settings control the "film look" applied to every generated image.</p>
            <div class="detail-field"><label>Lens Style</label><input data-field="lens_style" value="${_esc(cam.lens_style)}"></div>
            <div class="detail-field"><label>Film Stock</label><input data-field="film_stock" value="${_esc(cam.film_stock)}"></div>
            <div class="detail-field"><label>Color Grading</label><input data-field="color_grading" value="${_esc(cam.color_grading)}"></div>
            <div class="detail-field"><label>Lighting Philosophy</label><input data-field="lighting_philosophy" value="${_esc(cam.lighting_philosophy)}"></div>
            <div class="detail-field"><label>Movement Philosophy</label><input data-field="movement_philosophy" value="${_esc(cam.movement_philosophy)}"></div>
            <div class="detail-field"><label>Reference Films</label><input data-field="reference_films" value="${_esc(cam.reference_films)}"></div>
            <div class="detail-field">
                <label>Prompt Prefix (starts every image prompt)</label>
                <textarea data-field="prompt_prefix" rows="3" class="prompt-preview">${_esc(cam.prompt_prefix)}</textarea>
            </div>
            <div class="btn-group" style="margin-top:8px;">
                <button class="btn btn-secondary btn-sm" onclick="WorldBibleUI.saveCameraBible(${cam.id})">Save Changes</button>
            </div>
        </div>`;

        el.querySelectorAll('[data-field]').forEach(input => {
            input.onblur = () => this.saveCameraBible(cam.id);
        });
    },

    selectCamera() {
        State.set('wbTab', 'camera');
        this.render();
    },

    _renderRefGallery(refs, entityType) {
        if (!refs || refs.length === 0) {
            return '<div style="color:var(--text-dim);font-size:12px;padding:8px;">No references generated yet.</div>';
        }

        return refs.map(r => {
            const hasSrc = r.file_path;
            const src = hasSrc ? `/generated/${r.file_path}` : '';
            const approveMethod = entityType === 'character' ? 'approveCharRef' :
                                  entityType === 'location' ? 'approveLocRef' : 'approvePropRef';
            return `<div class="wb-ref-card ${r.is_approved ? 'approved' : ''}">
                <div class="wb-ref-img">
                    ${src ? `<img src="${src}" alt="${r.ref_type}">` : '<div class="wb-thumb-placeholder">?</div>'}
                </div>
                <div class="wb-ref-info">
                    <span class="wb-ref-type">${r.ref_type}</span>
                    ${r.is_approved ? '<span class="wb-ref-approved">Approved</span>' :
                    `<button class="btn btn-sm btn-secondary" onclick="WorldBibleUI.approveRef('${entityType}', ${r.id})">Approve</button>`}
                </div>
            </div>`;
        }).join('');
    },

    async saveEntity(type, id) {
        const el = document.getElementById('wb-detail');
        const data = {};
        el.querySelectorAll('[data-field]').forEach(input => {
            data[input.dataset.field] = input.value;
        });
        try {
            if (type === 'character') await API.updateCharacter(id, data);
            else if (type === 'location') await API.updateLocation(id, data);
            else if (type === 'prop') await API.updateProp(id, data);
            // Refresh world bible
            const story = State.get('currentStory');
            if (story) await this.loadWorldBible(story.id);
        } catch(e) {
            toast('Save failed: ' + e.message, 'error');
        }
    },

    async saveCameraBible(id) {
        const el = document.getElementById('wb-detail');
        const data = {};
        el.querySelectorAll('[data-field]').forEach(input => {
            data[input.dataset.field] = input.value;
        });
        try {
            await API.updateCameraBible(id, data);
            const story = State.get('currentStory');
            if (story) await this.loadWorldBible(story.id);
        } catch(e) {
            toast('Save failed: ' + e.message, 'error');
        }
    },

    async generateRefs(type, id) {
        try {
            toast(`Generating ${type} references...`, 'info');
            if (type === 'character') await API.generateCharRefs(id);
            else if (type === 'location') await API.generateLocRefs(id);
            else if (type === 'prop') await API.generatePropRefs(id);
        } catch(e) {
            toast('Generation failed: ' + e.message, 'error');
        }
    },

    async approveRef(entityType, refId) {
        try {
            if (entityType === 'character') await API.approveCharRef(refId);
            else if (entityType === 'location') await API.approveLocRef(refId);
            else if (entityType === 'prop') await API.approvePropRef(refId);
            toast('Reference approved!', 'success');
            const story = State.get('currentStory');
            if (story) await this.loadWorldBible(story.id);
        } catch(e) {
            toast('Approve failed: ' + e.message, 'error');
        }
    },

    handleWSMessage(data) {
        if (data.type === 'extraction_progress') {
            if (data.status === 'extracting' || data.status === 'refining') {
                toast(data.step || 'Extracting world bible...', 'info');
            } else if (data.status === 'complete') {
                toast('World bible extracted!', 'success');
                State.set('worldBible', data.world_bible);
                this.render();
                refreshCurrentStory();
            } else if (data.status === 'error') {
                toast('Extraction failed: ' + (data.error || 'Unknown error'), 'error');
            }
        } else if (data.type === 'reference_progress') {
            if (data.status === 'complete') {
                // Refresh world bible to show new refs
                const story = State.get('currentStory');
                if (story) this.loadWorldBible(story.id);
            } else if (data.status === 'error') {
                toast(`Reference generation failed for ${data.entity_type}`, 'error');
            }
        } else if (data.type === 'all_references_complete') {
            toast('All reference images generated!', 'success');
            const story = State.get('currentStory');
            if (story) this.loadWorldBible(story.id);
        }
    },
};

function _esc(s) { return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
