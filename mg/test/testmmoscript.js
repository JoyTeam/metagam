var assert = require('assert');
var mmoscript = require('../../static/js/mmoscript');
var MMOScript = mmoscript.MMOScript;
var DynamicValue = mmoscript.DynamicValue;
var Vec3 = mmoscript.Vec3;

assert(MMOScript);
assert(DynamicValue);
assert(Vec3);

/* Documentation: conversions from numbers to strings */
assert.strictEqual(MMOScript.evaluate(['+', '1', '2']), '12');
assert.strictEqual(MMOScript.evaluate(['+', '1', 2]), 3);
assert.strictEqual(MMOScript.evaluate(['-', '1', '2']), -1);
assert.strictEqual(MMOScript.evaluate(['*', '1', '2']), 2);
assert.strictEqual(MMOScript.evaluate(['/', '1', '2']), 0.5);
assert.strictEqual(MMOScript.evaluate(['/', undefined, '2']), 0);
assert.strictEqual(MMOScript.evaluate(['-', '15', 'test']), 15);

/* Documentation: comparsions */
assert.strictEqual(MMOScript.evaluate(['==', 1, 2]), 0);
assert.strictEqual(MMOScript.evaluate(['==', 1, 1]), 1);
assert.strictEqual(MMOScript.evaluate(['!=', 1, 2]), 1);
assert.strictEqual(MMOScript.evaluate(['!=', 1, 1]), 0);
assert.strictEqual(MMOScript.evaluate(['==', 'a', 'b']), 0);
assert.strictEqual(MMOScript.evaluate(['!=', 'a', 'b']), 1);
assert.strictEqual(MMOScript.evaluate(['>', 'a', 'b']), 0);
assert.strictEqual(MMOScript.evaluate(['<', 'a', 'b']), 0);

/* Addition */
assert.strictEqual(MMOScript.evaluate(['+', undefined, undefined]), undefined);
assert.strictEqual(MMOScript.evaluate(['+', undefined, 1]), 1);
assert.strictEqual(MMOScript.evaluate(['+', undefined, new Vec3(4, 5, 6)]).toString(), '(4, 5, 6)');
assert.strictEqual(MMOScript.evaluate(['+', undefined, 'hello']), 'hello');
assert.strictEqual(MMOScript.evaluate(['+', 1, undefined]), 1);
assert.strictEqual(MMOScript.evaluate(['+', 1, 3]), 4);
assert.strictEqual(MMOScript.evaluate(['+', 1, new Vec3(4, 5, 6)]), undefined);
assert.strictEqual(MMOScript.evaluate(['+', 1, 'hello']), 1);
assert.strictEqual(MMOScript.evaluate(['+', new Vec3(10, 11, 12), undefined]).toString(), '(10, 11, 12)');
assert.strictEqual(MMOScript.evaluate(['+', new Vec3(10, 11, 12), 3]), undefined);
assert.strictEqual(MMOScript.evaluate(['+', new Vec3(10, 11, 12), new Vec3(4, 5, 6)]).toString(), '(14, 16, 18)');
assert.strictEqual(MMOScript.evaluate(['+', new Vec3(10, 11, 12), 'hello']), undefined);
assert.strictEqual(MMOScript.evaluate(['+', '1.5', undefined]), '1.5');
assert.strictEqual(MMOScript.evaluate(['+', '1.5', 1]), 2.5);
assert.strictEqual(MMOScript.evaluate(['+', '1.5', new Vec3(1, 2, 3)]), undefined);
assert.strictEqual(MMOScript.evaluate(['+', 'foo', 'bar']), 'foobar');

/* Substraction */
assert.strictEqual(MMOScript.evaluate(['-', undefined, undefined]), undefined);
assert.strictEqual(MMOScript.evaluate(['-', undefined, 1]), -1);
assert.strictEqual(MMOScript.evaluate(['-', undefined, new Vec3(4, 5, 6)]).toString(), '(-4, -5, -6)');
assert.strictEqual(MMOScript.evaluate(['-', undefined, 'hello']), 0);
assert.strictEqual(MMOScript.evaluate(['-', 1, undefined]), 1);
assert.strictEqual(MMOScript.evaluate(['-', 1, 3]), -2);
assert.strictEqual(MMOScript.evaluate(['-', 1, new Vec3(4, 5, 6)]), undefined);
assert.strictEqual(MMOScript.evaluate(['-', 1, '8']), -7);
assert.strictEqual(MMOScript.evaluate(['-', new Vec3(10, 11, 12), undefined]).toString(), '(10, 11, 12)');
assert.strictEqual(MMOScript.evaluate(['-', new Vec3(10, 11, 12), 3]), undefined);
assert.strictEqual(MMOScript.evaluate(['-', new Vec3(10, 11, 12), new Vec3(4, 5, 6)]).toString(), '(6, 6, 6)');
assert.strictEqual(MMOScript.evaluate(['-', new Vec3(10, 11, 12), 'hello']), undefined);
assert.strictEqual(MMOScript.evaluate(['-', '5', undefined]), '5');
assert.strictEqual(MMOScript.evaluate(['-', '5.5', 1]), 4.5);
assert.strictEqual(MMOScript.evaluate(['-', 'foo', new Vec3(1, 2, 3)]), undefined);
assert.strictEqual(MMOScript.evaluate(['-', '8.5', '1.5']), 7);

/* Multiplication */
assert.strictEqual(MMOScript.evaluate(['*', undefined, undefined]), 0);
assert.strictEqual(MMOScript.evaluate(['*', undefined, 1]), 0);
assert.strictEqual(MMOScript.evaluate(['*', undefined, new Vec3(4, 5, 6)]).toString(), '(0, 0, 0)');
assert.strictEqual(MMOScript.evaluate(['*', undefined, 'hello']), 0);
assert.strictEqual(MMOScript.evaluate(['*', 1, undefined]), 0);
assert.strictEqual(MMOScript.evaluate(['*', 2, 3]), 6);
assert.strictEqual(MMOScript.evaluate(['*', 2, new Vec3(4, 5, 6)]).toString(), '(8, 10, 12)');
assert.strictEqual(MMOScript.evaluate(['*', 2, '8']), 16);
assert.strictEqual(MMOScript.evaluate(['*', new Vec3(10, 11, 12), undefined]).toString(), '(0, 0, 0)');
assert.strictEqual(MMOScript.evaluate(['*', new Vec3(10, 11, 12), 3]).toString(), '(30, 33, 36)');
assert.strictEqual(MMOScript.evaluate(['*', new Vec3(10, 11, 12), new Vec3(4, 5, 6)]).toString(), '(0, 0, 0)');
assert.strictEqual(MMOScript.evaluate(['*', new Vec3(10, 11, 12), '2']).toString(), '(20, 22, 24)');
assert.strictEqual(MMOScript.evaluate(['*', '5', undefined]), 0);
assert.strictEqual(MMOScript.evaluate(['*', '5.5', 2]), 11);
assert.strictEqual(MMOScript.evaluate(['*', '2.0', new Vec3(1, 2, 3)]).toString(), '(2, 4, 6)');
assert.strictEqual(MMOScript.evaluate(['*', '8.5', '1.5']), 12.75);

/* Division */
assert.strictEqual(MMOScript.evaluate(['/', undefined, undefined]), undefined);
assert.strictEqual(MMOScript.evaluate(['/', undefined, 1]), 0);
assert.strictEqual(MMOScript.evaluate(['/', undefined, new Vec3(4, 5, 6)]), undefined);
assert.strictEqual(MMOScript.evaluate(['/', undefined, '1.5']), 0);
assert.strictEqual(MMOScript.evaluate(['/', 1, undefined]), undefined);
assert.strictEqual(MMOScript.evaluate(['/', 3, 2]), 1.5);
assert.strictEqual(MMOScript.evaluate(['/', 2, new Vec3(4, 5, 6)]), undefined);
assert.strictEqual(MMOScript.evaluate(['/', 2, '4']), 0.5);
assert.strictEqual(MMOScript.evaluate(['/', new Vec3(10, 11, 12), undefined]), undefined);
assert.strictEqual(MMOScript.evaluate(['/', new Vec3(10, 11, 12), 2]).toString(), '(5, 5.5, 6)');
assert.strictEqual(MMOScript.evaluate(['/', new Vec3(10, 11, 12), new Vec3(4, 5, 6)]), undefined);
assert.strictEqual(MMOScript.evaluate(['/', new Vec3(10, 11, 12), '2']).toString(), '(5, 5.5, 6)');
assert.strictEqual(MMOScript.evaluate(['/', '5', undefined]), undefined);
assert.strictEqual(MMOScript.evaluate(['/', '4.5', 1.5]), 3);
assert.strictEqual(MMOScript.evaluate(['/', '2.0', new Vec3(1, 2, 3)]), undefined);
assert.strictEqual(MMOScript.evaluate(['/', '7.5', '1.5']), 5);

/* Division by zero */
assert.strictEqual(MMOScript.evaluate(['/', undefined, undefined]), undefined);
assert.strictEqual(MMOScript.evaluate(['/', undefined, 0]), undefined);
assert.strictEqual(MMOScript.evaluate(['/', undefined, '0']), undefined);
assert.strictEqual(MMOScript.evaluate(['/', 0, undefined]), undefined);
assert.strictEqual(MMOScript.evaluate(['/', 0, 0]), undefined);
assert.strictEqual(MMOScript.evaluate(['/', 0, '0']), undefined);
assert.strictEqual(MMOScript.evaluate(['/', new Vec3(1, 2, 3), undefined]), undefined);
assert.strictEqual(MMOScript.evaluate(['/', new Vec3(1, 2, 3), 0]), undefined);
assert.strictEqual(MMOScript.evaluate(['/', new Vec3(1, 2, 3), '0']), undefined);
assert.strictEqual(MMOScript.evaluate(['/', '5', undefined]), undefined);
assert.strictEqual(MMOScript.evaluate(['/', '5', 0]), undefined);
assert.strictEqual(MMOScript.evaluate(['/', '5', '0']), undefined);

/* Negation */
assert.strictEqual(MMOScript.evaluate(['-', undefined]), undefined);
assert.strictEqual(MMOScript.evaluate(['-', 1]), -1);
assert.strictEqual(MMOScript.evaluate(['-', new Vec3(1, 2, 3)]).toString(), '(-1, -2, -3)');
assert.strictEqual(MMOScript.evaluate(['-', '1.5']), -1.5);

/* Comparsion */
assert.strictEqual(MMOScript.evaluate(['==', undefined, undefined]), 1);
assert.strictEqual(MMOScript.evaluate(['<', undefined, undefined]), 0);
assert.strictEqual(MMOScript.evaluate(['>', undefined, undefined]), 0);
assert.strictEqual(MMOScript.evaluate(['!=', undefined, undefined]), 0);
assert.strictEqual(MMOScript.evaluate(['==', undefined, 0]), 0);
assert.strictEqual(MMOScript.evaluate(['!=', undefined, 0]), 1);
assert.strictEqual(MMOScript.evaluate(['>=', undefined, 0]), 1);
assert.strictEqual(MMOScript.evaluate(['<=', undefined, 0]), 1);
assert.strictEqual(MMOScript.evaluate(['<', undefined, 0]), 0);
assert.strictEqual(MMOScript.evaluate(['>', undefined, 0]), 0);
assert.strictEqual(MMOScript.evaluate(['<', 0, undefined]), 0);
assert.strictEqual(MMOScript.evaluate(['>', 0, undefined]), 0);
assert.strictEqual(MMOScript.evaluate(['<', undefined, 1]), 1);
assert.strictEqual(MMOScript.evaluate(['!=', undefined, 1]), 1);
assert.strictEqual(MMOScript.evaluate(['>', undefined, -1]), 1);
assert.strictEqual(MMOScript.evaluate(['!=', undefined, -1]), 1);
assert.strictEqual(MMOScript.evaluate(['<', undefined, '1']), 1);
assert.strictEqual(MMOScript.evaluate(['!=', undefined, '1']), 1);
assert.strictEqual(MMOScript.evaluate(['>', undefined, '-1']), 1);
assert.strictEqual(MMOScript.evaluate(['!=', undefined, '-1']), 1);
assert.strictEqual(MMOScript.evaluate(['!=', undefined, new Vec3(0, 0, 0)]), 1);
assert.strictEqual(MMOScript.evaluate(['==', 1, 1]), 1);
assert.strictEqual(MMOScript.evaluate(['<', 1, 2]), 1);
assert.strictEqual(MMOScript.evaluate(['>', 2, 1]), 1);
assert.strictEqual(MMOScript.evaluate(['>', 1, undefined]), 1);
assert.strictEqual(MMOScript.evaluate(['<', -1, undefined]), 1);
assert.strictEqual(MMOScript.evaluate(['==', 1, '1']), 1);
assert.strictEqual(MMOScript.evaluate(['!=', 1, '1']), 0);
assert.strictEqual(MMOScript.evaluate(['>=', 1, '1']), 1);
assert.strictEqual(MMOScript.evaluate(['<=', 1, '1']), 1);
assert.strictEqual(MMOScript.evaluate(['<', 1, '2']), 1);
assert.strictEqual(MMOScript.evaluate(['>', 1, '-2']), 1);
assert.strictEqual(MMOScript.evaluate(['!=', 0, new Vec3(0, 0, 0)]), 1);
assert.strictEqual(MMOScript.evaluate(['>=', 0, new Vec3(0, 0, 0)]), 1);
assert.strictEqual(MMOScript.evaluate(['<=', 0, new Vec3(0, 0, 0)]), 1);
assert.strictEqual(MMOScript.evaluate(['>', 1, new Vec3(0, 0, 0)]), 1);
assert.strictEqual(MMOScript.evaluate(['<', -1, new Vec3(0, 0, 0)]), 1);
assert.strictEqual(MMOScript.evaluate(['==', '1', 1]), 1);
assert.strictEqual(MMOScript.evaluate(['<', '1', 2]), 1);
assert.strictEqual(MMOScript.evaluate(['>', '1', undefined]), 1);
assert.strictEqual(MMOScript.evaluate(['<', '-1', undefined]), 1);
assert.strictEqual(MMOScript.evaluate(['==', '1.0', '1.0']), 1);
assert.strictEqual(MMOScript.evaluate(['==', '1.0', '1.00']), 0);
assert.strictEqual(MMOScript.evaluate(['<', '1.0', '2.0']), 1);
assert.strictEqual(MMOScript.evaluate(['>', '1.0', '2.0']), 0);
assert.strictEqual(MMOScript.evaluate(['>', 'foo', 'bar']), 0);
assert.strictEqual(MMOScript.evaluate(['<', 'foo', 'bar']), 0);
assert.strictEqual(MMOScript.evaluate(['!=', '0', new Vec3(0, 0, 0)]), 1);
assert.strictEqual(MMOScript.evaluate(['>=', '0', new Vec3(0, 0, 0)]), 1);
assert.strictEqual(MMOScript.evaluate(['<=', '0', new Vec3(0, 0, 0)]), 1);
assert.strictEqual(MMOScript.evaluate(['>', '1', new Vec3(0, 0, 0)]), 1);
assert.strictEqual(MMOScript.evaluate(['<', '-1', new Vec3(0, 0, 0)]), 1);
assert.strictEqual(MMOScript.evaluate(['!=', new Vec3(1.2, 1.3, 1.4), undefined]), 1);
assert.strictEqual(MMOScript.evaluate(['<=', new Vec3(1.2, 1.3, 1.4), undefined]), 1);
assert.strictEqual(MMOScript.evaluate(['>=', new Vec3(1.2, 1.3, 1.4), undefined]), 1);
assert.strictEqual(MMOScript.evaluate(['!=', new Vec3(1.2, 1.3, 1.4), 0]), 1);
assert.strictEqual(MMOScript.evaluate(['<=', new Vec3(1.2, 1.3, 1.4), 0]), 1);
assert.strictEqual(MMOScript.evaluate(['>=', new Vec3(1.2, 1.3, 1.4), 0]), 1);
assert.strictEqual(MMOScript.evaluate(['<', new Vec3(1.2, 1.3, 1.4), 1]), 1);
assert.strictEqual(MMOScript.evaluate(['>', new Vec3(1.2, 1.3, 1.4), -1]), 1);
assert.strictEqual(MMOScript.evaluate(['!=', new Vec3(1.2, 1.3, 1.4), '0']), 1);
assert.strictEqual(MMOScript.evaluate(['<=', new Vec3(1.2, 1.3, 1.4), '0']), 1);
assert.strictEqual(MMOScript.evaluate(['>=', new Vec3(1.2, 1.3, 1.4), '0']), 1);
assert.strictEqual(MMOScript.evaluate(['<', new Vec3(1.2, 1.3, 1.4), '1']), 1);
assert.strictEqual(MMOScript.evaluate(['>', new Vec3(1.2, 1.3, 1.4), '-1']), 1);
assert.strictEqual(MMOScript.evaluate(['==', new Vec3(1.2, 1.3, 1.4), new Vec3(1.2, 1.3, 1.4)]), 1);
assert.strictEqual(MMOScript.evaluate(['>', new Vec3(1.2, 1.3, 1.5), new Vec3(1.2, 1.3, 1.4)]), 1);
assert.strictEqual(MMOScript.evaluate(['<', new Vec3(1.2, 1.3, 1.3), new Vec3(1.2, 1.3, 1.4)]), 1);
assert.strictEqual(MMOScript.evaluate(['>', new Vec3(1.2, 1.4, 1.4), new Vec3(1.2, 1.3, 1.5)]), 1);

/* Modules */
assert.strictEqual(MMOScript.evaluate(['%', 7, 4]), 3);
assert.strictEqual(MMOScript.evaluate(['%', 7, 0]), undefined);

/* Vectors */
assert.strictEqual(MMOScript.evaluate(['call', 'vec3', 1, 2, 3]).toString(), '(1, 2, 3)');

/* True/false */
assert.strictEqual(MMOScript.evaluate(['not', 0]), 1);
assert.strictEqual(MMOScript.evaluate(['not', 1]), 0);
assert.strictEqual(MMOScript.evaluate(['not', '']), 1);
assert.strictEqual(MMOScript.evaluate(['not', '0']), 0);
assert.strictEqual(MMOScript.evaluate(['not', undefined]), 1);

/* Dates */
assert(MMOScript.evaluate(['.', ['now'], 'utc_year']) >= 2000);
assert(MMOScript.evaluate(['.', ['now'], 'utc_year']) <= 3000);
assert.strictEqual(typeof(MMOScript.evaluate(['.', ['now'], 'utc_year'])), 'number');
assert.strictEqual(typeof(MMOScript.evaluate(['.', ['now'], 'utc_month'])), 'number');
assert.strictEqual(typeof(MMOScript.evaluate(['.', ['now'], 'utc_day'])), 'number');
assert.strictEqual(typeof(MMOScript.evaluate(['.', ['now'], 'utc_hour'])), 'number');
assert.strictEqual(typeof(MMOScript.evaluate(['.', ['now'], 'utc_minute'])), 'number');
assert.strictEqual(typeof(MMOScript.evaluate(['.', ['now'], 'utc_second'])), 'number');
