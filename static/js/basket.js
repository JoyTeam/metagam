function Basket()
{
	this.dna_list = new Array();
	this.basket = new Array();
}

Basket.prototype.register = function(dna, price, currency, cicon) {
	this.dna_list.push({
		dna: dna,
		price: price,
		currency: currency,
		cicon: cicon
	});
	this.basket[dna] = this.get(dna);
};

Basket.prototype.get = function(dna) {
	var qparam = 'q_' + dna;
	var value = parseInt(document.getElementById(qparam).value);
	if (value == NaN || value < 0) {
		value = 0;
	}
	return value;
};

Basket.prototype.update = function(dna) {
	this.basket[dna] = this.get(dna);
	this.render();
};

Basket.prototype.render = function() {
	var total = new Array();
	var currencies = new Array();
	var entries = new Array();
	for (var i = 0; i < this.dna_list.length; i++) {
		var ent = this.dna_list[i];
		var value = this.basket[ent.dna];
		if (value > 0) {
			entries.push(ent.dna + '/' + ent.price + '/' + ent.currency + '/' + value);
			if (total[ent.currency]) {
				total[ent.currency] += ent.price * value;
			} else {
				total[ent.currency] = ent.price * value;
				currencies.push({
					code: ent.currency,
					icon: ent.cicon
				});
			}
		}
	}
	var form = document.getElementById('shop-basket-form');
	var cost = document.getElementById('shop-basket-cost');
	if (cost) {
		if (currencies.length) {
			var html = '';
			for (i = 0; i < currencies.length; i++) {
				var cur = currencies[i];
				html += '<div class="price shop-cost-entry"><span class="money-amount">' + total[cur.code] + '</span> <span class="money-currency"><img src="' + cur.icon + '" alt="' + cur.code + '" /></span></div>';
			}
			cost.innerHTML = html;
			if (form)
				form.style.display = 'block';
		} else if (form) {
			form.style.display = 'none';
		}
	} else if (form) {
		form.style.display = 'none';
	}
	var items = document.getElementById('shop-basket-items');
	if (items) {
		items.value = entries.join(';');
	}
};

loaded('basket');
