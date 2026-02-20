/**
 * Storybook — Main Application
 */

// ===== Toast Notifications =====
function toast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => el.remove(), 4000);
}

// ===== View Management =====
function showView(name) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const el = document.getElementById(`view-${name}`);
    if (el) el.classList.add('active');
    State.set('view', name);

    // Update sidebar nav
    document.querySelectorAll('.sidebar-nav button').forEach(b => {
        b.classList.toggle('active', b.dataset.view === name);
    });

    // Load world bible data when switching to that view
    if (name === 'world-bible') {
        const story = State.get('currentStory');
        if (story) WorldBibleUI.loadWorldBible(story.id);
    }
}

// ===== Story List (sidebar) =====
async function loadStories() {
    try {
        const stories = await API.listStories();
        State.set('stories', stories);
        renderStoryList();
    } catch(e) {
        toast('Failed to load stories: ' + e.message, 'error');
    }
}

function renderStoryList() {
    const el = document.getElementById('story-list');
    const stories = State.get('stories');
    const current = State.get('currentStory');
    el.innerHTML = stories.length ? stories.map(s => `
        <div class="story-item ${current && current.id === s.id ? 'active' : ''}" data-id="${s.id}">
            <div>${s.title}</div>
            <div class="status">${s.status} &middot; ${s.scene_count} scenes &middot; ${s.shot_count} shots</div>
        </div>
    `).join('') : '<div style="padding:12px;color:var(--text-dim);font-size:12px;">No stories yet</div>';

    el.querySelectorAll('.story-item').forEach(item => {
        item.onclick = () => selectStory(parseInt(item.dataset.id));
    });
}

async function selectStory(id) {
    try {
        State.set('loading', true);
        const story = await API.getStoryFull(id);
        State.set('currentStory', story);
        State.set('selectedScene', null);
        State.set('selectedShot', null);
        renderStoryList();
        showView('timeline');
        renderTimeline();
        updateHeader();
        updateHeaderButtons();
    } catch(e) {
        toast('Failed to load story: ' + e.message, 'error');
    } finally {
        State.set('loading', false);
    }
}

function updateHeader() {
    const story = State.get('currentStory');
    const el = document.getElementById('header-title');
    el.textContent = story ? story.title : 'Storybook';
}

function updateHeaderButtons() {
    const story = State.get('currentStory');
    const btnPrompts = document.getElementById('btn-prompts');
    const btnGenerate = document.getElementById('btn-generate');
    const btnGenerateVideos = document.getElementById('btn-generate-videos');

    if (!story) {
        btnPrompts.disabled = true;
        btnGenerate.disabled = true;
        btnGenerateVideos.disabled = true;
        return;
    }

    // Count total shots across story
    let totalShots = 0;
    let shotsWithPrompts = 0;
    let shotsWithImages = 0;
    for (const ch of (story.chapters || [])) {
        for (const sc of ch.scenes) {
            for (const sh of (sc.shots || [])) {
                totalShots++;
                if (sh.image_prompt) shotsWithPrompts++;
                if (sh.current_image && sh.current_image.file_path) shotsWithImages++;
            }
        }
    }

    // Build Prompts: enabled when shots exist
    btnPrompts.disabled = totalShots === 0;
    // Generate All: enabled when shots have prompts
    btnGenerate.disabled = shotsWithPrompts === 0;
    // Generate Videos: enabled when shots have images
    btnGenerateVideos.disabled = shotsWithImages === 0;
}

// ===== Create Story =====
async function handleCreateStory(e) {
    e.preventDefault();
    const form = e.target;
    const title = form.querySelector('[name=title]').value.trim();
    const raw_text = form.querySelector('[name=raw_text]').value.trim();
    const visual_style = form.querySelector('[name=visual_style]').value.trim();
    const music_style = form.querySelector('[name=music_style]').value.trim();

    if (!title || !raw_text) { toast('Title and story text required', 'error'); return; }

    try {
        State.set('loading', true);
        const story = await API.createStory({ title, raw_text, visual_style, music_style });
        toast('Story created!', 'success');
        form.reset();
        await loadStories();
        await selectStory(story.id);
    } catch(e) {
        toast('Create failed: ' + e.message, 'error');
    } finally {
        State.set('loading', false);
    }
}

// ===== Timeline Rendering =====
function renderTimeline() {
    const story = State.get('currentStory');
    if (!story) return;

    renderSourceStrip(story);
    renderSceneCards(story);
    renderShotCards();
    renderDetailPanel();
}

function renderSourceStrip(story) {
    const el = document.getElementById('source-strip');
    if (!story.chapters || story.chapters.length === 0) {
        el.innerHTML = `<div style="color:var(--text-dim)">No chapters yet. Click <strong>Segment</strong> to analyze the story.</div>`;
        return;
    }
    let html = '';
    for (const ch of story.chapters) {
        html += `<strong style="color:var(--accent)">[${ch.title || 'Chapter ' + (ch.order_index + 1)}]</strong>\n`;
        for (const sc of ch.scenes) {
            html += `<span class="scene-marker" data-scene="${sc.id}">S${sc.order_index + 1}</span> `;
            html += (sc.source_text || sc.goal || '').substring(0, 150) + '...\n';
        }
    }
    el.innerHTML = html;
    el.querySelectorAll('.scene-marker').forEach(m => {
        m.onclick = () => {
            State.set('selectedScene', parseInt(m.dataset.scene));
            renderSceneCards(story);
            renderShotCards();
            renderDetailPanel();
        };
    });
}

function renderSceneCards(story) {
    if (!story) story = State.get('currentStory');
    const el = document.getElementById('scene-cards');
    if (!story || !story.chapters) { el.innerHTML = ''; return; }

    const selectedScene = State.get('selectedScene');
    const breakingDown = State.get('breakingDownScenes');
    const allScenes = story.chapters.flatMap(ch => ch.scenes);

    el.innerHTML = allScenes.map(sc => {
        const width = Math.max(180, sc.target_duration * 5);
        const bgGrad = getEmotionGradient(sc.opening_emotion, sc.closing_emotion);
        const intensityPct = Math.round((sc.intensity || 0.5) * 100);
        const intensityColor = sc.intensity > 0.7 ? 'var(--red)' : sc.intensity > 0.4 ? 'var(--orange)' : 'var(--green)';

        // Breakdown status
        const isBreakingDown = breakingDown.has(sc.id);
        const hasShots = sc.shot_count > 0;
        const statusClass = isBreakingDown ? 'breaking-down' : hasShots ? 'broken-down' : 'not-broken-down';

        // Scene type badge
        const typeBadge = sc.scene_type === 'sequel'
            ? '<span class="scene-type-badge sequel">Sequel</span>'
            : '<span class="scene-type-badge scene">Scene</span>';

        // Shot status display
        const shotStatus = isBreakingDown
            ? '<span class="shot-status breaking"><span class="spinner-sm"></span> Breaking down...</span>'
            : hasShots
                ? `<span class="shot-status has-shots">${sc.shot_count} shots</span>`
                : `<span class="shot-status no-shots">No shots</span>`;

        // Per-scene breakdown button (only when no shots and not breaking down)
        const breakdownBtn = !hasShots && !isBreakingDown
            ? `<button class="btn btn-sm scene-breakdown-btn" onclick="event.stopPropagation(); breakdownScene(${sc.id})">Break Down</button>`
            : '';

        return `
        <div class="scene-card ${statusClass} ${selectedScene === sc.id ? 'selected' : ''}"
             data-id="${sc.id}" style="width:${width}px; background:${bgGrad}">
            <div class="scene-card-top">
                ${typeBadge}
                <span class="scene-num">S${sc.order_index + 1}</span>
            </div>
            <div class="scene-goal">${esc(sc.goal || sc.emotion || 'No goal set')}</div>
            <div class="scene-meta">
                <span>${sc.target_duration}s</span>
                ${shotStatus}
            </div>
            ${sc.opening_emotion ? `<span class="emotion-badge">${sc.opening_emotion} → ${sc.closing_emotion || '?'}</span>` : ''}
            <div class="intensity-bar"><div class="fill" style="width:${intensityPct}%;background:${intensityColor}"></div></div>
            ${breakdownBtn}
        </div>`;
    }).join('');

    el.querySelectorAll('.scene-card').forEach(card => {
        card.onclick = () => {
            const id = parseInt(card.dataset.id);
            State.set('selectedScene', id);
            State.set('selectedShot', null);
            renderSceneCards(story);
            renderShotCards();
            renderDetailPanel();
        };
    });
}

function getEmotionGradient(opening, closing) {
    const emotionColors = {
        'fear': '#1a0a2e', 'tension': '#1a1535', 'dread': '#150d25',
        'confusion': '#1a1a35', 'curiosity': '#15202e', 'wonder': '#0f2035',
        'anger': '#2e1515', 'rage': '#351010', 'despair': '#201015',
        'hope': '#152a20', 'relief': '#153025', 'joy': '#1a2e15',
        'sadness': '#151a2e', 'melancholy': '#1a152e', 'grief': '#1e1025',
        'shock': '#2e2015', 'surprise': '#2e2515', 'determination': '#1e2515',
        'resignation': '#1e1e25', 'triumph': '#252e15', 'power': '#251520',
    };
    const c1 = emotionColors[opening?.toLowerCase()] || 'var(--surface)';
    const c2 = emotionColors[closing?.toLowerCase()] || c1;
    return `linear-gradient(135deg, ${c1}, ${c2})`;
}

function renderShotCards() {
    const el = document.getElementById('shot-cards');
    const story = State.get('currentStory');
    const selectedScene = State.get('selectedScene');
    const selectedShot = State.get('selectedShot');
    const breakingDown = State.get('breakingDownScenes');

    if (!story || !selectedScene) {
        el.innerHTML = '<div style="padding:12px;color:var(--text-dim);font-size:12px;">Select a scene to view shots</div>';
        return;
    }

    // Find the scene
    let scene = null;
    for (const ch of (story.chapters || [])) {
        for (const sc of ch.scenes) {
            if (sc.id === selectedScene) { scene = sc; break; }
        }
        if (scene) break;
    }

    // Show loading spinner if scene is being broken down
    if (scene && (!scene.shots || scene.shots.length === 0) && breakingDown.has(selectedScene)) {
        el.innerHTML = `<div class="breakdown-loading">
            <div class="spinner"></div>
            <div class="breakdown-loading-text">Breaking down scene into shots...</div>
            <div class="breakdown-loading-sub">Claude is analyzing the scene for visual direction, camera angles, and color scripting.</div>
        </div>`;
        return;
    }

    if (!scene || !scene.shots || scene.shots.length === 0) {
        el.innerHTML = '<div style="padding:12px;color:var(--text-dim);font-size:12px;">No shots yet. Click <strong>Break Down</strong> on the scene card or use <strong>Breakdown All</strong>.</div>';
        return;
    }

    el.innerHTML = scene.shots.map(sh => {
        const hasImage = sh.current_image && sh.current_image.file_path;
        const hasVideo = sh.current_video && sh.current_video.file_path;
        const imgSrc = hasImage ? `/generated/${sh.current_image.file_path}` : '';
        const swatches = (sh.color_palette || []).map(c => `<div class="swatch" style="background:${c}"></div>`).join('');
        const transColor = { dissolve: 'var(--blue)', fade: 'var(--text-dim)', wipe: 'var(--orange)', cut: 'transparent' };
        const vidStatus = sh.video_generation_status || 'pending';
        return `
        <div class="shot-card ${selectedShot === sh.id ? 'selected' : ''}" data-id="${sh.id}" draggable="true">
            <div class="thumb">
                ${hasImage ? `<img src="${imgSrc}" alt="Shot ${sh.order_index + 1}">` : '&#9633;'}
                <div class="duration-badge">${sh.duration}s</div>
                <div class="status-dot ${sh.generation_status}"></div>
                <button class="shot-card-gen-btn" onclick="event.stopPropagation(); generateShot(${sh.id})" title="Generate Image">&#9654;</button>
                ${hasImage ? `<button class="shot-card-vid-btn ${vidStatus === 'generating' ? 'generating' : ''}" onclick="event.stopPropagation(); generateShotVideo(${sh.id})" title="Generate Video">&#9654;&#9654;</button>` : ''}
            </div>
            <div class="shot-info">
                <div class="shot-type">${sh.shot_type || 'shot'} ${sh.order_index + 1}${hasVideo ? ' <span style="color:var(--green)">&#9658;</span>' : ''}</div>
                <div class="shot-desc">${sh.description || ''}</div>
                <div class="color-swatches">${swatches}</div>
            </div>
            <div class="transition-indicator" style="background:${transColor[sh.transition_type] || 'transparent'}"></div>
        </div>`;
    }).join('');

    // Click and drag handlers
    el.querySelectorAll('.shot-card').forEach(card => {
        card.onclick = () => {
            State.set('selectedShot', parseInt(card.dataset.id));
            renderShotCards();
            renderDetailPanel();
        };
        card.ondragstart = (e) => {
            e.dataTransfer.setData('text/plain', card.dataset.id);
            card.classList.add('dragging');
        };
        card.ondragend = () => card.classList.remove('dragging');
        card.ondragover = (e) => { e.preventDefault(); card.classList.add('drag-over'); };
        card.ondragleave = () => card.classList.remove('drag-over');
        card.ondrop = async (e) => {
            e.preventDefault();
            card.classList.remove('drag-over');
            const fromId = parseInt(e.dataTransfer.getData('text/plain'));
            const toId = parseInt(card.dataset.id);
            if (fromId === toId) return;
            const cards = [...el.querySelectorAll('.shot-card')];
            const ids = cards.map(c => parseInt(c.dataset.id));
            const fromIdx = ids.indexOf(fromId);
            const toIdx = ids.indexOf(toId);
            ids.splice(fromIdx, 1);
            ids.splice(toIdx, 0, fromId);
            try {
                await API.reorderShots(ids);
                await refreshCurrentStory();
            } catch(err) { toast('Reorder failed: ' + err.message, 'error'); }
        };
    });
}

function renderDetailPanel() {
    const el = document.getElementById('detail-panel');
    const story = State.get('currentStory');
    const selectedScene = State.get('selectedScene');
    const selectedShot = State.get('selectedShot');

    if (selectedShot && story) {
        const shot = findShot(story, selectedShot);
        if (shot) { renderShotDetail(el, shot); return; }
    }
    if (selectedScene && story) {
        const scene = findScene(story, selectedScene);
        if (scene) { renderSceneDetail(el, scene); return; }
    }

    el.innerHTML = `<div class="empty-state"><div class="icon">&#9661;</div><h3>Select a scene or shot</h3><p>Click on a scene card to view its details, or select a shot to edit.</p></div>`;
}

function findScene(story, id) {
    for (const ch of (story.chapters || [])) {
        for (const sc of ch.scenes) { if (sc.id === id) return sc; }
    }
    return null;
}

function findShot(story, id) {
    for (const ch of (story.chapters || [])) {
        for (const sc of ch.scenes) {
            for (const sh of (sc.shots || [])) { if (sh.id === id) return sh; }
        }
    }
    return null;
}

function renderSceneDetail(el, scene) {
    const breakingDown = State.get('breakingDownScenes');
    const isBreaking = breakingDown.has(scene.id);

    el.innerHTML = `
    <div class="detail-content">
        <div class="detail-left">
            <h3>Scene ${scene.order_index + 1} — ${scene.scene_type}</h3>
            <div class="detail-field"><label>Goal</label><textarea data-field="goal" rows="2">${esc(scene.goal)}</textarea></div>
            <div class="detail-field"><label>Conflict</label><textarea data-field="conflict" rows="2">${esc(scene.conflict)}</textarea></div>
            <div class="detail-field"><label>Outcome</label><textarea data-field="outcome" rows="2">${esc(scene.outcome)}</textarea></div>
            ${scene.scene_type === 'sequel' ? `
            <div class="detail-field"><label>Emotion</label><textarea data-field="emotion" rows="1">${esc(scene.emotion)}</textarea></div>
            <div class="detail-field"><label>Logic</label><textarea data-field="logic" rows="1">${esc(scene.logic)}</textarea></div>
            <div class="detail-field"><label>Decision</label><textarea data-field="decision" rows="1">${esc(scene.decision)}</textarea></div>
            ` : ''}
            <div class="detail-field"><label>Opening Emotion</label><input data-field="opening_emotion" value="${esc(scene.opening_emotion)}"></div>
            <div class="detail-field"><label>Closing Emotion</label><input data-field="closing_emotion" value="${esc(scene.closing_emotion)}"></div>
            <div class="detail-field"><label>Intensity (0-1)</label><input type="number" step="0.1" min="0" max="1" data-field="intensity" value="${scene.intensity}"></div>
            <div class="detail-field"><label>Duration (seconds)</label><input type="number" data-field="target_duration" value="${scene.target_duration}"></div>
        </div>
        <div class="detail-right">
            <h3>Source Text</h3>
            <div style="background:var(--surface2);padding:12px;border-radius:var(--radius);font-size:13px;line-height:1.6;max-height:400px;overflow-y:auto;white-space:pre-wrap;">${esc(scene.source_text)}</div>
            <div style="margin-top:12px;" class="btn-group">
                <button class="btn btn-secondary btn-sm" onclick="breakdownScene(${scene.id})" ${isBreaking ? 'disabled' : ''}>
                    ${isBreaking ? '<span class="spinner-sm"></span> Breaking Down...' : 'Break Down Shots'}
                </button>
            </div>
        </div>
    </div>`;
}

function renderShotDetail(el, shot) {
    const hasImage = shot.current_image && shot.current_image.file_path;
    const hasVideo = shot.current_video && shot.current_video.file_path;
    const imgSrc = hasImage ? `/generated/${shot.current_image.file_path}` : '';
    const vidSrc = hasVideo ? `/generated/${shot.current_video.file_path}` : '';
    const paletteHtml = (shot.color_palette || []).map((c, i) =>
        `<input type="color" value="${c}" data-palette-idx="${i}" style="width:30px;height:24px;border:none;padding:0;cursor:pointer;">`
    ).join(' ');

    el.innerHTML = `
    <div class="detail-content">
        <div class="detail-left">
            <h3>Shot ${shot.order_index + 1}</h3>
            <div class="detail-field"><label>Description</label><textarea data-field="description" rows="2">${esc(shot.description)}</textarea></div>
            <div class="detail-field"><label>Dialogue</label><textarea data-field="dialogue" rows="1">${esc(shot.dialogue)}</textarea></div>
            <div class="detail-field">
                <label>Shot Type</label>
                <select data-field="shot_type">
                    ${['wide','medium','close-up','extreme-close-up','over-the-shoulder','birds-eye','low-angle','dutch-angle','pov'].map(t =>
                        `<option ${shot.shot_type===t?'selected':''}>${t}</option>`).join('')}
                </select>
            </div>
            <div class="detail-field">
                <label>Camera Movement</label>
                <select data-field="camera_movement">
                    ${['static','pan','tilt','zoom','dolly','crane','tracking','handheld','steadicam'].map(t =>
                        `<option ${shot.camera_movement===t?'selected':''}>${t}</option>`).join('')}
                </select>
            </div>
            <div class="detail-field"><label>Camera Detail</label><input data-field="camera_movement_detail" value="${esc(shot.camera_movement_detail)}"></div>
            <div class="detail-field"><label>Lighting</label><input data-field="lighting" value="${esc(shot.lighting)}"></div>
            <div class="detail-field"><label>Color Mood</label><input data-field="color_mood" value="${esc(shot.color_mood)}"></div>
            <div class="detail-field"><label>Color Palette</label><div>${paletteHtml || '<span style="color:var(--text-dim);font-size:12px;">No palette set</span>'}</div></div>
            <div class="detail-field"><label>Duration (s)</label><input type="number" step="0.5" min="1" max="15" data-field="duration" value="${shot.duration}"></div>
            <div class="detail-field">
                <label>Transition</label>
                <select data-field="transition_type">
                    ${['cut','dissolve','fade','wipe'].map(t => `<option ${shot.transition_type===t?'selected':''}>${t}</option>`).join('')}
                </select>
            </div>
            <h3 style="margin-top:16px;">Music</h3>
            <div class="detail-field"><label>Tempo</label><input data-field="music_tempo" value="${esc(shot.music_tempo)}"></div>
            <div class="detail-field"><label>Mood</label><input data-field="music_mood" value="${esc(shot.music_mood)}"></div>
            <div class="detail-field"><label>Instruments</label><input data-field="music_instruments" value="${esc(shot.music_instruments)}"></div>
        </div>
        <div class="detail-right">
            <h3>Image</h3>
            <div class="image-preview">
                ${hasImage ? `<img src="${imgSrc}">` : '<div class="placeholder">No image generated yet</div>'}
            </div>
            <div class="detail-field" style="margin-top:12px;">
                <label>Image Prompt</label>
                <textarea data-field="image_prompt" rows="4">${esc(shot.image_prompt)}</textarea>
            </div>
            <div class="btn-group" style="margin-top:8px;">
                <button class="btn btn-primary btn-sm" onclick="generateShot(${shot.id})">Generate Image</button>
                <button class="btn btn-secondary btn-sm" onclick="saveShotEdits(${shot.id})">Save Changes</button>
            </div>
            <div style="margin-top:6px;font-size:11px;color:var(--text-dim);">Image status: <strong>${shot.generation_status}</strong></div>

            <h3 style="margin-top:20px;">Video</h3>
            <div class="video-preview">
                ${hasVideo ? `<video src="${vidSrc}" controls></video>` : '<div class="placeholder">No video generated yet</div>'}
            </div>
            <div class="detail-field" style="margin-top:12px;">
                <label>Video Prompt</label>
                <textarea data-field="video_prompt" rows="3">${esc(shot.video_prompt)}</textarea>
            </div>
            <div class="btn-group" style="margin-top:8px;">
                <button class="btn btn-sm ${hasImage ? 'btn-primary' : 'btn-secondary'}" onclick="generateShotVideo(${shot.id})" ${hasImage ? '' : 'disabled'}>Generate Video</button>
            </div>
            <div style="margin-top:6px;font-size:11px;color:var(--text-dim);">Video status: <strong>${shot.video_generation_status || 'pending'}</strong></div>
        </div>
    </div>`;

    el.querySelectorAll('[data-field]').forEach(input => {
        input.onblur = () => saveShotEdits(shot.id);
    });
}

function esc(s) { return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

// ===== Actions =====
async function segmentStory() {
    const story = State.get('currentStory');
    if (!story) return;
    try {
        State.set('loading', true);
        toast('Segmenting story...', 'info');
        await API.segmentStory(story.id);
        toast('Segmentation complete!', 'success');
        await refreshCurrentStory();
    } catch(e) {
        toast('Segmentation failed: ' + e.message, 'error');
    } finally {
        State.set('loading', false);
    }
}

async function breakdownScene(sceneId) {
    const breakingDown = State.get('breakingDownScenes');
    if (breakingDown.has(sceneId)) return; // Already breaking down

    breakingDown.add(sceneId);
    State.set('breakingDownScenes', breakingDown);
    renderSceneCards();
    renderShotCards();

    try {
        toast('Breaking down scene...', 'info');
        await API.breakdownScene(sceneId);
        // Actual completion comes via WebSocket
    } catch(e) {
        breakingDown.delete(sceneId);
        State.set('breakingDownScenes', breakingDown);
        toast('Breakdown failed: ' + e.message, 'error');
        renderSceneCards();
        renderShotCards();
    }
}

async function breakdownAll() {
    const story = State.get('currentStory');
    if (!story) return;

    // Mark all scenes without shots as breaking down
    const breakingDown = State.get('breakingDownScenes');
    for (const ch of (story.chapters || [])) {
        for (const sc of ch.scenes) {
            if (sc.shot_count === 0) breakingDown.add(sc.id);
        }
    }
    State.set('breakingDownScenes', breakingDown);
    renderSceneCards();

    try {
        toast('Breaking down all scenes...', 'info');
        await API.breakdownAll(story.id);
        // Actual completion comes via WebSocket
    } catch(e) {
        toast('Breakdown failed: ' + e.message, 'error');
    }
}

async function extractWorld() {
    const story = State.get('currentStory');
    if (!story) return;
    try {
        toast('Extracting world bible...', 'info');
        await API.extractWorldBible(story.id);
        // Completion comes via WebSocket
    } catch(e) {
        toast('Extraction failed: ' + e.message, 'error');
    }
}

async function buildPrompts() {
    const story = State.get('currentStory');
    if (!story) return;
    try {
        toast('Building image prompts...', 'info');
        await API.buildPrompts(story.id);
        toast('Prompts built!', 'success');
        await refreshCurrentStory();
    } catch(e) {
        toast('Prompt building failed: ' + e.message, 'error');
    }
}

async function generateShot(shotId) {
    try {
        toast('Generating image...', 'info');
        await API.generateShot(shotId);
    } catch(e) {
        toast('Generation failed: ' + e.message, 'error');
    }
}

async function generateShotVideo(shotId) {
    try {
        toast('Generating video...', 'info');
        await API.generateShotVideo(shotId);
    } catch(e) {
        toast('Video generation failed: ' + e.message, 'error');
    }
}

async function generateAllVideos() {
    const story = State.get('currentStory');
    if (!story) return;
    try {
        toast('Generating all videos...', 'info');
        await API.generateAllVideos(story.id);
    } catch(e) {
        toast('Video generation failed: ' + e.message, 'error');
    }
}

async function generateAll() {
    const story = State.get('currentStory');
    if (!story) return;
    try {
        State.set('loading', true);
        toast('Generating all images...', 'info');
        await API.generateAll(story.id);
    } catch(e) {
        toast('Generation failed: ' + e.message, 'error');
    } finally {
        State.set('loading', false);
    }
}

async function saveShotEdits(shotId) {
    const panel = document.getElementById('detail-panel');
    const data = {};
    panel.querySelectorAll('[data-field]').forEach(input => {
        let val = input.value;
        if (input.type === 'number') val = parseFloat(val);
        data[input.dataset.field] = val;
    });
    const paletteInputs = panel.querySelectorAll('[data-palette-idx]');
    if (paletteInputs.length > 0) {
        data.color_palette = [...paletteInputs].map(i => i.value);
    }
    try {
        await API.updateShot(shotId, data);
    } catch(e) {
        toast('Save failed: ' + e.message, 'error');
    }
}

async function refreshCurrentStory() {
    const story = State.get('currentStory');
    if (!story) return;
    const updated = await API.getStoryFull(story.id);
    State.set('currentStory', updated);
    renderTimeline();
    updateHeaderButtons();
    await loadStories();
}

// ===== WebSocket handler =====
function handleWSMessage(data) {
    if (data.type === 'shot_progress') {
        const story = State.get('currentStory');
        if (!story) return;
        const shot = findShot(story, data.shot_id);
        if (shot) {
            shot.generation_status = data.status;
            if (data.image) shot.current_image = data.image;
            renderShotCards();
            if (State.get('selectedShot') === data.shot_id) renderDetailPanel();
        }
    } else if (data.type === 'generation_complete') {
        toast('Generation batch complete!', 'success');
        refreshCurrentStory();
    } else if (data.type === 'video_progress') {
        const story = State.get('currentStory');
        if (!story) return;
        const shot = findShot(story, data.shot_id);
        if (shot) {
            shot.video_generation_status = data.status;
            if (data.video) shot.current_video = data.video;
            renderShotCards();
            if (State.get('selectedShot') === data.shot_id) renderDetailPanel();
        }
    } else if (data.type === 'video_generation_scene_complete') {
        toast('Scene video sequence complete!', 'success');
        refreshCurrentStory();
    } else if (data.type === 'video_generation_complete') {
        toast('All videos generated!', 'success');
        refreshCurrentStory();
    } else if (data.type === 'breakdown_progress') {
        const breakingDown = State.get('breakingDownScenes');
        if (data.status === 'started') {
            breakingDown.add(data.scene_id);
        } else if (data.status === 'complete') {
            breakingDown.delete(data.scene_id);
            toast(`Scene breakdown complete! ${data.shot_count} shots created.`, 'success');
            refreshCurrentStory();
        } else if (data.status === 'error') {
            breakingDown.delete(data.scene_id);
            toast('Breakdown error: ' + (data.error || 'Unknown'), 'error');
        }
        State.set('breakingDownScenes', breakingDown);
        renderSceneCards();
        if (State.get('selectedScene') === data.scene_id) {
            renderShotCards();
        }
    } else if (data.type === 'breakdown_all_complete') {
        toast(`All breakdowns complete! ${data.total_shots} total shots.`, 'success');
        refreshCurrentStory();
    }

    // Delegate to WorldBibleUI
    WorldBibleUI.handleWSMessage(data);
}

// ===== Init =====
document.addEventListener('DOMContentLoaded', () => {
    // Sidebar nav
    document.querySelectorAll('.sidebar-nav button').forEach(btn => {
        btn.onclick = () => showView(btn.dataset.view);
    });

    // Create story form
    document.getElementById('create-story-form').addEventListener('submit', handleCreateStory);

    // Header action buttons
    document.getElementById('btn-segment').onclick = segmentStory;
    document.getElementById('btn-extract-world').onclick = extractWorld;
    document.getElementById('btn-breakdown').onclick = breakdownAll;
    document.getElementById('btn-prompts').onclick = buildPrompts;
    document.getElementById('btn-generate').onclick = generateAll;
    document.getElementById('btn-generate-videos').onclick = generateAllVideos;

    // WebSocket
    WS.connect();
    WS.onMessage(handleWSMessage);

    // World Bible UI
    WorldBibleUI.init();

    // Resize handles
    initResizeHandles();
    restoreLaneHeights();

    // Load stories
    loadStories();
    showView('create');
});

// ===== Resizable Timeline Lanes =====
function initResizeHandles() {
    document.querySelectorAll('.resize-handle').forEach(handle => {
        handle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            const aboveId = handle.dataset.above;
            const belowId = handle.dataset.below;
            const aboveEl = document.getElementById(aboveId);
            const belowEl = document.getElementById(belowId);
            if (!aboveEl || !belowEl) return;

            const startY = e.clientY;
            const startAboveH = aboveEl.offsetHeight;
            const startBelowH = belowEl.offsetHeight;
            const minH = 60;

            handle.classList.add('dragging');

            function onMove(e) {
                const delta = e.clientY - startY;
                const newAbove = Math.max(minH, startAboveH + delta);
                const newBelow = Math.max(minH, startBelowH - delta);
                // Only apply if both above minimum
                if (newAbove >= minH && newBelow >= minH) {
                    aboveEl.style.height = newAbove + 'px';
                    belowEl.style.height = newBelow + 'px';
                }
            }

            function onUp() {
                handle.classList.remove('dragging');
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
                saveLaneHeights();
            }

            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    });
}

function saveLaneHeights() {
    const ids = ['lane-source', 'lane-scenes', 'lane-shots', 'detail-panel'];
    const heights = {};
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) heights[id] = el.offsetHeight;
    });
    try { localStorage.setItem('storybook-lane-heights', JSON.stringify(heights)); } catch(e) {}
}

function restoreLaneHeights() {
    try {
        const saved = JSON.parse(localStorage.getItem('storybook-lane-heights'));
        if (!saved) return;
        Object.entries(saved).forEach(([id, h]) => {
            const el = document.getElementById(id);
            if (el && h >= 60) el.style.height = h + 'px';
        });
    } catch(e) {}
}
