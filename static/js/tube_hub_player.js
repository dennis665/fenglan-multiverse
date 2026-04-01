// 取得 DOM 元素
const modeSwitch = document.getElementById('modeSwitch');
const videoPlayer = document.getElementById('videoPlayer');
const audioPlayer = document.getElementById('audioPlayer');
const audioWrapper = document.getElementById('audioWrapper');
const speedSlider = document.getElementById('speedSlider');
const speedValue = document.getElementById('speedValue');

// A-B Loop 相關變數
let loopA = null;
let loopB = null;
const btnSetA = document.getElementById('btnSetA');
const btnSetB = document.getElementById('btnSetB');
const btnClearAB = document.getElementById('btnClearAB');
const abLoopToggle = document.getElementById('abLoopToggle');
const labelA = document.getElementById('labelA');
const labelB = document.getElementById('labelB');

// 取得當前作用中的播放器 (影片或音訊)
function getActivePlayer() {
    if (modeSwitch && modeSwitch.checked) {
        return videoPlayer;
    }
    return audioWrapper.classList.contains('d-none') ? videoPlayer : audioPlayer;
}

// 格式化秒數為時間字串
function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
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
    });
}

// 統一語速控制
if (speedSlider) {
    speedSlider.addEventListener('input', (e) => {
        const speed = parseFloat(e.target.value);
        speedValue.textContent = speed.toFixed(1);
        videoPlayer.playbackRate = speed;
        audioPlayer.playbackRate = speed;
    });
}

// 處理快進與倒退 (5s/10s)
document.querySelectorAll('.btn-skip').forEach(btn => {
    btn.addEventListener('click', () => {
        const seconds = parseInt(btn.dataset.seconds);
        const player = getActivePlayer();
        player.currentTime = Math.max(0, player.currentTime + seconds);
    });
});

// A-B 段落重複播放邏輯
btnSetA.addEventListener('click', () => {
    const player = getActivePlayer();
    loopA = player.currentTime;
    labelA.textContent = `A: ${formatTime(loopA)}`;
    labelA.classList.add('text-info');
});

btnSetB.addEventListener('click', () => {
    const player = getActivePlayer();
    loopB = player.currentTime;
    labelB.textContent = `B: ${formatTime(loopB)}`;
    labelB.classList.add('text-info');
});

btnClearAB.addEventListener('click', () => {
    loopA = null;
    loopB = null;
    abLoopToggle.checked = false;
    labelA.textContent = 'A: --:--';
    labelB.textContent = 'B: --:--';
    labelA.classList.remove('text-info');
    labelB.classList.remove('text-info');
});

// 監聽播放時間實現循環
const handleTimeUpdate = (e) => {
    if (abLoopToggle.checked && loopA !== null && loopB !== null) {
        const player = e.target;
        if (player.currentTime >= loopB || player.currentTime < loopA) {
            player.currentTime = loopA;
        }
    }
};

videoPlayer.addEventListener('timeupdate', handleTimeUpdate);
audioPlayer.addEventListener('timeupdate', handleTimeUpdate);