document.addEventListener("DOMContentLoaded", () => {

    const symbolInput = document.getElementById("symbol");

    symbolInput.addEventListener("keyup", () => {
        const symbol = symbolInput.value.trim();
        if (symbol.length < 1) {
            document.getElementById("openPositions").innerHTML = "";
            return;
        }

        fetch(`/api/open_positions/${symbol}`)
            .then(response => response.json())
            .then(data => {
                let html = "";

                if (data.length === 0) {
                    html = "<p>No open positions.</p>";
                } else {
                    html = "<ul>";
                    data.forEach(pos => {
                        html += `<li>${pos.quantity} @ strike ${pos.strike}, exp ${pos.expiration}, side ${pos.side}</li>`;
                    });
                    html += "</ul>";
                }

                document.getElementById("openPositions").innerHTML = html;
            });
    });

});