// 取得 DOM 元素
const modeSwitch = document.getElementById('modeSwitch');
const loopToggle = document.getElementById('loopToggle'); // 新增全曲循環開關
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

// ======= 全新：Three.js 3D 立體櫻花背景邏輯 =======
function initThreeJSCherryBlossoms() {
    const container = document.getElementById('three-bg-container');
    if (!container) return;

    // 建立場景、相機與渲染器
    const scene = new THREE.Scene();

    // 設定相機的視角 (FOV)，數值越大透視感越強
    const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 1, 1000);
    camera.position.z = 200; // 相機位置

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true }); // alpha: true 允許背景透明
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    // 建立櫻花粒子系統
    const particleCount = 1500; // 粒子密度 (可依需求調整，1500 算高密度)
    const geometry = new THREE.BufferGeometry();
    const positions = [];
    const sizes = [];
    const velocities = []; // 紀錄每個粒子的掉落速度與風向

    for (let i = 0; i < particleCount; i++) {
        // 在 3D 空間隨機散佈粒子 (x, y, z)
        positions.push(
            (Math.random() - 0.5) * 800, // X 軸寬度
            Math.random() * 800 - 400,   // Y 軸高度 (從畫面上方到底部)
            (Math.random() - 0.5) * 600  // Z 軸深度 (產生立體感的核心)
        );

        // 隨機大小
        sizes.push(Math.random() * 3 + 1.5);

        // 隨機掉落速度與飄動幅度
        velocities.push({
            y: -(Math.random() * 0.5 + 0.2), // 下落速度
            x: (Math.random() - 0.5) * 0.2,  // 橫向飄動 (風)
            z: (Math.random() - 0.5) * 0.2,  // 前後飄動
            angle: Math.random() * Math.PI * 2, // 旋轉角度
            spinSpeed: (Math.random() - 0.5) * 0.1
        });
    }

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute('size', new THREE.Float32BufferAttribute(sizes, 1));

    // 建立材質：使用 ShaderMaterial 來繪製圓形的粉色櫻花瓣
    const material = new THREE.ShaderMaterial({
        uniforms: {
            color: { value: new THREE.Color(0xffb7c5) } // 櫻花粉色
        },
        vertexShader: `
            attribute float size;
            varying vec3 vPosition;
            void main() {
                vPosition = position;
                vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
                // 根據 Z 軸深度調整大小，越遠越小
                gl_PointSize = size * (300.0 / -mvPosition.z); 
                gl_Position = projectionMatrix * mvPosition;
            }
        `,
        fragmentShader: `
            uniform vec3 color;
            void main() {
                // 將方形的點變成柔和的圓形
                vec2 coord = gl_PointCoord - vec2(0.5);
                if (length(coord) > 0.5) discard;
                
                // 邊緣羽化，增加真實感
                float alpha = 1.0 - smoothstep(0.3, 0.5, length(coord));
                gl_FragColor = vec4(color, alpha * 0.8);
            }
        `,
        transparent: true,
        depthWrite: false // 避免粒子互相遮擋產生黑邊
    });

    const particleSystem = new THREE.Points(geometry, material);
    scene.add(particleSystem);

    // 動畫迴圈
    function animate() {
        requestAnimationFrame(animate);

        const positions = particleSystem.geometry.attributes.position.array;

        // 更新每個粒子的位置
        for (let i = 0; i < particleCount; i++) {
            const i3 = i * 3;
            const vel = velocities[i];

            // 加入正弦波函數，讓櫻花有搖曳飄落的感覺
            positions[i3] += vel.x + Math.sin(vel.angle) * 0.1; // X 軸搖曳
            positions[i3 + 1] += vel.y;                         // Y 軸下落
            positions[i3 + 2] += vel.z + Math.cos(vel.angle) * 0.05; // Z 軸搖曳

            vel.angle += vel.spinSpeed; // 更新搖曳角度

            // 如果掉到畫面最底部，就讓它從上面重新出現
            if (positions[i3 + 1] < -400) {
                positions[i3 + 1] = 400;
                positions[i3] = (Math.random() - 0.5) * 800; // 重置 X 位置
                positions[i3 + 2] = (Math.random() - 0.5) * 600; // 重置 Z 深度
            }
        }

        particleSystem.geometry.attributes.position.needsUpdate = true;

        // 讓整個粒子系統緩慢旋轉，增加大空間的立體錯覺
        particleSystem.rotation.y += 0.0005;

        renderer.render(scene, camera);
    }

    animate();

    // 4. 處理視窗縮放
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
}
// 啟動動畫
initThreeJSCherryBlossoms();
// =============================

// ======= Web Audio API 與 Tone.js 升降 Key 引擎 =======
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
        console.log("🎵 Tone.js 音效引擎已成功啟動");
    } catch (error) {
        console.error("啟動音效引擎失敗:", error);
    }
}

// 必須有使用者互動才能啟動 Web Audio
document.body.addEventListener('click', () => {
    if (!isAudioInitialized) initPitchShifter();
}, { once: true });

// 處理升降 Key 滑桿拖拉事件
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
// =======================================================

// 取得當前作用中的播放器
function getActivePlayer() {
    if (modeSwitch && modeSwitch.checked) return videoPlayer;
    return audioWrapper.classList.contains('d-none') ? videoPlayer : audioPlayer;
}

function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
}

// --- 全曲循環邏輯 ---
function handleLoop() {
    const player = getActivePlayer();
    if (loopToggle && loopToggle.checked) {
        player.loop = true;
    } else {
        player.loop = false;
    }
}

if (loopToggle) {
    loopToggle.addEventListener('change', handleLoop);
}

// 處理 KTV 模式切換
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
        handleLoop(); // 確保切換模式後，循環設定依然有效
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

// 快進快退
document.querySelectorAll('.btn-skip').forEach(btn => {
    btn.addEventListener('click', () => {
        const seconds = parseInt(btn.dataset.seconds);
        const player = getActivePlayer();
        player.currentTime = Math.max(0, player.currentTime + seconds);
    });
});

// A-B Loop 邏輯
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

const handleTimeUpdate = (e) => {
    // 優先處理 A-B Loop
    if (abLoopToggle && abLoopToggle.checked && loopA !== null && loopB !== null) {
        const player = e.target;
        if (player.currentTime >= loopB || player.currentTime < loopA) {
            player.currentTime = loopA;
        }
    }
};

if (videoPlayer) videoPlayer.addEventListener('timeupdate', handleTimeUpdate);
if (audioPlayer) audioPlayer.addEventListener('timeupdate', handleTimeUpdate);

// ======= 儲存個人筆記邏輯 =======
const btnSaveNotes = document.getElementById('btnSaveNotes');
const personalNotesInput = document.getElementById('personalNotesInput');
const saveStatusMsg = document.getElementById('saveStatusMsg');
const resourceIdInput = document.getElementById('resourceId');

if (btnSaveNotes && personalNotesInput && resourceIdInput) {
    btnSaveNotes.addEventListener('click', async () => {
        // 改變按鈕狀態，避免重複點擊
        const originalText = btnSaveNotes.innerHTML;
        btnSaveNotes.disabled = true;
        btnSaveNotes.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> 儲存中...';

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
                // 顯示儲存成功的提示訊息，2.5 秒後消失
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
            // 恢復按鈕狀態
            btnSaveNotes.disabled = false;
            btnSaveNotes.innerHTML = originalText;
        }
    });
}