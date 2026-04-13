// 取得 DOM 元素
const modeSwitch = document.getElementById('modeSwitch'); //* 切換 KTV 模式
const loopToggle = document.getElementById('loopToggle'); //* 單一資源的全曲循環開關
const videoPlayer = document.getElementById('videoPlayer');
const audioPlayer = document.getElementById('audioPlayer');
const audioWrapper = document.getElementById('audioWrapper');
const speedSlider = document.getElementById('speedSlider');
const speedValue = document.getElementById('speedValue');
const pitchSlider = document.getElementById('pitchSlider');
const pitchValue = document.getElementById('pitchValue');

// A-B Loop 相關變數
let loopA = null;
let loopB = null;
const btnSetA = document.getElementById('btnSetA');
const btnSetB = document.getElementById('btnSetB');
const btnClearAB = document.getElementById('btnClearAB');
const abLoopToggle = document.getElementById('abLoopToggle');
const labelA = document.getElementById('labelA');
const labelB = document.getElementById('labelB');

// 播放清單與播放模式相關變數
const playModeBtns = document.querySelectorAll('.play-mode-btn');
const btnNextSong = document.getElementById('btnNextSong');
let currentPlayMode = localStorage.getItem('tubeHubPlayMode') || 'loop_all';

// Three.js 3D 立體櫻花背景邏輯
function initThreeJSCherryBlossoms() {
    const container = document.getElementById('three-bg-container');
    if (!container) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 1, 1000);
    camera.position.z = 200;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    const particleCount = 1500;
    const geometry = new THREE.BufferGeometry();
    const positions = [];
    const sizes = [];
    const velocities = [];

    for (let i = 0; i < particleCount; i++) {
        positions.push(
            (Math.random() - 0.5) * 800,
            Math.random() * 800 - 400,
            (Math.random() - 0.5) * 600
        );

        sizes.push(Math.random() * 3 + 1.5);

        velocities.push({
            y: -(Math.random() * 0.5 + 0.2),
            x: (Math.random() - 0.5) * 0.2,
            z: (Math.random() - 0.5) * 0.2,
            angle: Math.random() * Math.PI * 2,
            spinSpeed: (Math.random() - 0.5) * 0.1
        });
    }

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute('size', new THREE.Float32BufferAttribute(sizes, 1));

    const material = new THREE.ShaderMaterial({
        uniforms: {
            color: { value: new THREE.Color(0xffb7c5) }
        },
        vertexShader: `
            attribute float size;
            varying vec3 vPosition;
            void main() {
                vPosition = position;
                vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
                gl_PointSize = size * (300.0 / -mvPosition.z); 
                gl_Position = projectionMatrix * mvPosition;
            }
        `,
        fragmentShader: `
            uniform vec3 color;
            void main() {
                vec2 coord = gl_PointCoord - vec2(0.5);
                if (length(coord) > 0.5) discard;
                float alpha = 1.0 - smoothstep(0.3, 0.5, length(coord));
                gl_FragColor = vec4(color, alpha * 0.8);
            }
        `,
        transparent: true,
        depthWrite: false
    });

    const particleSystem = new THREE.Points(geometry, material);
    scene.add(particleSystem);

    function animate() {
        requestAnimationFrame(animate);

        const positions = particleSystem.geometry.attributes.position.array;

        for (let i = 0; i < particleCount; i++) {
            const i3 = i * 3;
            const vel = velocities[i];

            positions[i3] += vel.x + Math.sin(vel.angle) * 0.1;
            positions[i3 + 1] += vel.y;
            positions[i3 + 2] += vel.z + Math.cos(vel.angle) * 0.05;

            vel.angle += vel.spinSpeed;

            if (positions[i3 + 1] < -400) {
                positions[i3 + 1] = 400;
                positions[i3] = (Math.random() - 0.5) * 800;
                positions[i3 + 2] = (Math.random() - 0.5) * 600;
            }
        }

        particleSystem.geometry.attributes.position.needsUpdate = true;
        particleSystem.rotation.y += 0.0005;

        renderer.render(scene, camera);
    }

    animate();

    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
}

initThreeJSCherryBlossoms();

// Web Audio API 與 Tone.js 升降 Key 引擎
let isAudioInitialized = false;
let pitchShiftEffect = null;

async function initPitchShifter() {
    if (isAudioInitialized) return;

    try {
        await Tone.start();
        pitchShiftEffect = new Tone.PitchShift(0).toDestination();

        if (videoPlayer) {
            const videoSource = Tone.context.createMediaElementSource(videoPlayer);
            Tone.connect(videoSource, pitchShiftEffect);
        }

        if (audioPlayer && audioPlayer.querySelector('source')) {
            const audioSource = Tone.context.createMediaElementSource(audioPlayer);
            Tone.connect(audioSource, pitchShiftEffect);
        }

        isAudioInitialized = true;
        console.log("Tone.js 音效引擎已成功啟動");
    } catch (error) {
        console.error("啟動音效引擎失敗:", error);
    }
}

document.body.addEventListener('click', () => {
    if (!isAudioInitialized) initPitchShifter();
}, { once: true });

if (pitchSlider) {
    pitchSlider.addEventListener('input', async (e) => {
        const pitch = parseInt(e.target.value);

        pitchValue.textContent = pitch > 0 ? `+${pitch}` : pitch;
        pitchValue.className = pitch === 0 ? "text-warning fw-bold" : "text-danger fw-bold";

        if (!isAudioInitialized) await initPitchShifter();

        if (pitchShiftEffect) {
            pitchShiftEffect.pitch = pitch;
        }
    });
}

// 取得當前作用中的播放器
function getActivePlayer() {
    if (modeSwitch && modeSwitch.checked) return videoPlayer;
    return audioWrapper.classList.contains('d-none') ? videoPlayer : audioPlayer;
}

// 初始化音量與自動播放狀態
function initPlayerState() {
    const player = getActivePlayer();

    // 從瀏覽器本地儲存讀取並設定音量
    const savedVolume = localStorage.getItem('tubeHubVolume');
    if (savedVolume !== null) {
        player.volume = parseFloat(savedVolume);
    }

    // 監聽音量變化並儲存，確保下一首維持一樣的音量
    player.addEventListener('volumechange', (e) => {
        localStorage.setItem('tubeHubVolume', e.target.volume);
    });

    // 檢查網址是否有 autoplay 參數 (歌單切歌時會傳遞此參數) //* 確保順暢切換自動播
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('autoplay') === '1') {
        player.play().catch(e => console.log('自動播放被瀏覽器阻擋:', e));
    }
}

// 確保資源載入後執行初始化
if (videoPlayer) videoPlayer.addEventListener('loadedmetadata', initPlayerState);
if (audioPlayer) audioPlayer.addEventListener('loadedmetadata', initPlayerState);

// 格式化時間秒數
function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
}

// 處理原生循環播放邏輯
function handleLoop() {
    const player = getActivePlayer();

    // 如果是歌單模式，交由 JS ended 事件處理循環，取消原生 loop 屬性
    if (window.playlistItems && window.playlistItems.length > 0) {
        player.loop = false;
        return;
    }

    // 處理非歌單狀態下的傳統全曲循環
    if (loopToggle && loopToggle.checked) {
        player.loop = true;
    } else {
        player.loop = false;
    }
}

if (loopToggle) {
    loopToggle.addEventListener('change', handleLoop);
}

// KTV 模式切換
if (modeSwitch) {
    modeSwitch.addEventListener('change', (e) => {
        videoPlayer.pause();
        audioPlayer.pause();
        if (e.target.checked) {
            videoPlayer.classList.remove('d-none');
            audioWrapper.classList.add('d-none');
        } else {
            videoPlayer.classList.add('d-none');
            audioWrapper.classList.remove('d-none');
        }
        handleLoop(); 
    });
}

// 語速控制
if (speedSlider) {
    speedSlider.addEventListener('input', (e) => {
        const speed = parseFloat(e.target.value);
        speedValue.textContent = speed.toFixed(1);

        if (videoPlayer) videoPlayer.playbackRate = speed;
        if (audioPlayer && audioPlayer.currentSrc) {
            audioPlayer.playbackRate = speed;
        }
    });
}

// 快進快退按鈕
document.querySelectorAll('.btn-skip').forEach(btn => {
    btn.addEventListener('click', () => {
        const seconds = parseInt(btn.dataset.seconds);
        const player = getActivePlayer();
        player.currentTime = Math.max(0, player.currentTime + seconds);
    });
});

// A-B Loop 段落重複設定
if (btnSetA) {
    btnSetA.addEventListener('click', () => {
        loopA = getActivePlayer().currentTime;
        labelA.textContent = `A: ${formatTime(loopA)}`;
        labelA.classList.add('text-info');
    });
}

if (btnSetB) {
    btnSetB.addEventListener('click', () => {
        loopB = getActivePlayer().currentTime;
        labelB.textContent = `B: ${formatTime(loopB)}`;
        labelB.classList.add('text-info');
    });
}

if (btnClearAB) {
    btnClearAB.addEventListener('click', () => {
        loopA = null;
        loopB = null;
        abLoopToggle.checked = false;
        labelA.textContent = 'A: --:--';
        labelB.textContent = 'B: --:--';
        labelA.classList.remove('text-info');
        labelB.classList.remove('text-info');
    });
}

// 監聽播放進度事件
const handleTimeUpdate = (e) => {
    // 處理 A-B Loop 區間限制
    if (abLoopToggle && abLoopToggle.checked && loopA !== null && loopB !== null) {
        const player = e.target;
        if (player.currentTime >= loopB || player.currentTime < loopA) {
            player.currentTime = loopA;
        }
    }
};

if (videoPlayer) videoPlayer.addEventListener('timeupdate', handleTimeUpdate);
if (audioPlayer) audioPlayer.addEventListener('timeupdate', handleTimeUpdate);

// 更新歌單播放模式 UI 狀態
function updatePlayModeUI() {
    playModeBtns.forEach(btn => {
        if (btn.dataset.mode === currentPlayMode) {
            btn.classList.remove('btn-outline-warning');
            btn.classList.add('btn-warning', 'text-dark');
        } else {
            btn.classList.remove('btn-warning', 'text-dark');
            btn.classList.add('btn-outline-warning');
        }
    });
}

// 綁定歌單播放模式按鈕事件
if (playModeBtns.length > 0) {
    updatePlayModeUI();
    playModeBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            currentPlayMode = e.currentTarget.dataset.mode;
            localStorage.setItem('tubeHubPlayMode', currentPlayMode);
            updatePlayModeUI();
        });
    });
}

// 切換下一首邏輯
function playNextSong(forceNext = false) {
    if (!window.playlistItems || window.playlistItems.length === 0) return;

    let nextId = window.currentResourceId;
    const currentIndex = window.playlistItems.findIndex(item => item.id === nextId);

    if (currentPlayMode === 'loop_single' && !forceNext) {
        // 單曲循環：重新播放當前歌曲
        const player = getActivePlayer();
        player.currentTime = 0;
        player.play();
        return;
    } else if (currentPlayMode === 'shuffle') {
        // 隨機播放
        if (window.playlistItems.length > 1) {
            let randomIndex = currentIndex;
            while (randomIndex === currentIndex) {
                randomIndex = Math.floor(Math.random() * window.playlistItems.length);
            }
            nextId = window.playlistItems[randomIndex].id;
        }
    } else {
        // 全部循環 或 使用者強制點擊下一首
        if (currentIndex !== -1) {
            const nextIndex = (currentIndex + 1) % window.playlistItems.length;
            nextId = window.playlistItems[nextIndex].id;
        }
    }

    if (nextId !== window.currentResourceId) {
        // 加入 ?autoplay=1 讓下一首頁面載入時能觸發自動播放 //* 解決不會自動播放的問題
        window.location.href = `/tube_hub/player/${nextId}/?autoplay=1`;
    }
}

if (btnNextSong) {
    btnNextSong.addEventListener('click', () => playNextSong(true));
}

// 處理播放結束事件
const handleEnded = (e) => {
    if (window.playlistItems && window.playlistItems.length > 0) {
        // 觸發歌單切歌邏輯
        playNextSong();
    } else {
        // 舊有單一資源的循環邏輯
        if (loopToggle && loopToggle.checked) {
            e.target.currentTime = 0;
            e.target.play();
        }
    }
};

if (videoPlayer) videoPlayer.addEventListener('ended', handleEnded);
if (audioPlayer) audioPlayer.addEventListener('ended', handleEnded);

// 儲存個人筆記邏輯
const btnSaveNotes = document.getElementById('btnSaveNotes');
const personalNotesInput = document.getElementById('personalNotesInput');
const saveStatusMsg = document.getElementById('saveStatusMsg');
const resourceIdInput = document.getElementById('resourceId');

if (btnSaveNotes && personalNotesInput && resourceIdInput) {
    btnSaveNotes.addEventListener('click', async () => {
        const originalText = btnSaveNotes.innerHTML;
        btnSaveNotes.disabled = true;
        btnSaveNotes.innerHTML = '儲存中...';

        const formData = new URLSearchParams();
        formData.append('resource_id', resourceIdInput.value);
        formData.append('notes_content', personalNotesInput.value);

        try {
            const response = await fetch('/tube_hub/update_notes/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData.toString()
            });
            const data = await response.json();

            if (data.status === 'success') {
                saveStatusMsg.classList.remove('d-none');
                setTimeout(() => {
                    saveStatusMsg.classList.add('d-none');
                }, 2500);
            } else {
                alert('儲存失敗: ' + (data.message || '未知錯誤'));
            }
        } catch (error) {
            console.error('儲存筆記發生錯誤:', error);
            alert('系統發生錯誤，無法儲存筆記。');
        } finally {
            btnSaveNotes.disabled = false;
            btnSaveNotes.innerHTML = originalText;
        }
    });
}