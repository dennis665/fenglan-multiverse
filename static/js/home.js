// 首頁互動邏輯 (Home Page Interaction)
document.addEventListener('DOMContentLoaded', () => {
    const wrapper = document.querySelector('.cyber-wrapper');

    if (wrapper) {
        // 監聽滑鼠移動，動態更新 CSS 變數控制電流位置
        wrapper.addEventListener('mousemove', e => {
            const rect = wrapper.getBoundingClientRect();
            const x = ((e.clientX - rect.left) / rect.width) * 100;
            const y = ((e.clientY - rect.top) / rect.height) * 100;
            wrapper.style.setProperty('--mouse-x', `${x}%`);
            wrapper.style.setProperty('--mouse-y', `${y}%`);
        });
    }
});