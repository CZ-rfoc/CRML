// 全局DOM加载完成后执行
document.addEventListener("DOMContentLoaded", function() {
    // 1. 渲染Flash消息（自动消失3秒）
    const flashMessages = document.querySelectorAll(".flash-messages");
    flashMessages.forEach(msg => {
        setTimeout(() => {
            msg.style.opacity = 0;
            setTimeout(() => msg.remove(), 500);
        }, 3000);
    });

    // 2. 头像上传：点击头像触发文件选择（修复重复弹出+提交逻辑）
    const avatarImg = document.getElementById("avatar-img");
    const avatarInput = document.getElementById("avatar-input");
    const avatarForm = document.getElementById("avatar-form");
    const avatarTip = document.getElementById("avatar-tip"); // 新增：提示框元素
    if (avatarImg && avatarInput && avatarForm) {
        // 点击头像触发文件选择（阻断冒泡和默认行为）
        avatarImg.addEventListener("click", (e) => {
            e.stopPropagation(); // 阻止事件冒泡到父表单
            e.preventDefault(); // 阻断浏览器默认点击行为
            avatarInput.click(); // 仅触发一次文件选择
        });

        // 预览头像 + 异步提交表单（核心修复）
        avatarInput.addEventListener("change", (e) => {
            e.stopPropagation(); // 阻止事件扩散
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (r) => {
                    // 预览头像
                    avatarImg.src = r.target.result;
                    // 显示成功提示（如果有提示框）
                    if (avatarTip) {
                        avatarTip.style.display = "block";
                        setTimeout(() => {
                            avatarTip.style.display = "none";
                        }, 2000);
                    }
                };
                reader.readAsDataURL(file);

                // 异步提交表单（避免同步提交的重复问题）
                const formData = new FormData(avatarForm);
                fetch(avatarForm.action, {
                    method: "POST",
                    body: formData,
                }).catch(err => console.error("头像提交失败：", err));

                // 重置输入框，避免重复选择同一文件时不触发change事件
                avatarInput.value = "";
            }
        });

        // 阻断表单默认提交行为（关键：避免同步提交触发二次弹窗）
        avatarForm.addEventListener("submit", (e) => {
            e.preventDefault();
        });

        // 阻止表单点击事件冒泡（额外防护）
        avatarForm.addEventListener("click", (e) => e.stopPropagation());
    }

    // 3. ECharts图表渲染：用户主页（名次概率饼图+最近10战折线图）
    renderCharts();

    // 4. 对局管理：素点录入实时求和验证
    const scoreInputs = document.querySelectorAll("[name^='score_']");
    const scoreTotal = document.getElementById("score-total");
    if (scoreInputs.length && scoreTotal) {
        scoreInputs.forEach(input => {
            input.addEventListener("input", calculateScoreTotal);
        });
        // 初始化求和
        calculateScoreTotal();
    }

    // 5. 对局管理：勾选玩家数量验证（必须4个）
    const gameForm = document.getElementById("game-form");
    if (gameForm) {
        gameForm.addEventListener("submit", (e) => {
            if (parseInt(scoreTotal.innerText) !==100000) {
                e.preventDefault();
                alert(`素点总和必须为100000！当前：${scoreTotal.innerText}`);
            }
        });
    }
});

// 计算素点总和
function calculateScoreTotal() {
    let total = 0;
    const scoreInputs = document.querySelectorAll("[name^='score_']");
    scoreInputs.forEach(input => {
        total += parseInt(input.value) || 0;
    });
    document.getElementById("score-total").innerText = total;
    // 颜色提示：正确绿色，错误红色
    scoreTotal.style.color = total ===100000 ? "#28a745" : "#dc3545";
}

// 渲染ECharts图表
function renderCharts() {
    // 名次概率饼图
    const rankChartDom = document.getElementById("rank-chart");
    if (rankChartDom) {
        const rankChart = echarts.init(rankChartDom);
        const rankRate = JSON.parse(rankChartDom.dataset.rate);
        const option = {
            title: { text: "顺位率", left: "center", fontSize: 16 },
            tooltip: { trigger: "item" },
            legend: { orient: "horizontal", bottom: 0, left: "center" },
            series: [{
                name: "对局次数",
                type: "pie",
                radius: ["40%", "70%"],
                data: [
                    { value: rankRate[0], name: "1位" },
                    { value: rankRate[1], name: "2位" },
                    { value: rankRate[2], name: "3位" },
                    { value: rankRate[3], name: "4位" }
                ],
                color: ["#d62929", "#ffc107", "#28a745", "#6c757d"]
            }]
        };
        rankChart.setOption(option);
        // 自适应窗口大小
        window.addEventListener("resize", () => rankChart.resize());
    }

    // 最近10战名次折线图
    const trendChartDom = document.getElementById("trend-chart");
    if (trendChartDom) {
        const last10Ranks = JSON.parse(trendChartDom.dataset.ranks);
        const xData = last10Ranks.map((_, i) => `第${i+1}战`);
        const trendChart = echarts.init(trendChartDom);
        const option = {
            title: { text: "最近10战顺位", left: "center", fontSize: 16 },
            tooltip: { trigger: "axis" },
            xAxis: { type: "category", data: xData },
            yAxis: {
                type: "value",
                min:1, max:4,
                interval:1,
                // 名次倒序：1位在顶部
                inverse: true
            },
            series: [{
                data: last10Ranks,
                type: "line",
                symbol: "circle",
                symbolSize: 8,
                lineWidth: 2,
                color: "#d62929"
            }]
        };
        trendChart.setOption(option);
        window.addEventListener("resize", () => trendChart.resize());
    }
}