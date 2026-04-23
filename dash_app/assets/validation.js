window.validators = {
  isIntList: function(value) {
    if (value === null || value === undefined) return false;
    var text = String(value).trim();
    if (!text) return false;
    var tokens = text.split(/[\s,]+/).filter(Boolean);
    if (!tokens.length) return false;
    return tokens.every(function(tok) {
      return /^\d+$/.test(tok) && parseInt(tok, 10) > 0;
    });
  },
  isPositiveInt: function(value, minValue) {
    var min = (typeof minValue === "number") ? minValue : 1;
    if (value === null || value === undefined || value === "") return false;
    var n = Number(value);
    return Number.isInteger(n) && n >= min;
  },
  isFloat: function(value, minValue, maxValue, strictMin) {
    if (value === null || value === undefined || value === "") return false;
    var n = Number(value);
    if (!Number.isFinite(n)) return false;
    if (minValue !== null && minValue !== undefined) {
      if (strictMin ? n <= minValue : n < minValue) return false;
    }
    if (maxValue !== null && maxValue !== undefined && n > maxValue) return false;
    return true;
  }
};

window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.validation = window.dash_clientside.validation || {};

window.dash_clientside.validation.validate_generation_inputs = function(
  nodeCount,
  seed,
  sigma,
  meanRev,
  maxMult,
  forbidProb,
  restoreProb,
  maxDisabled
) {
  var v = window.validators;
  var msg = "Parametres valides";
  var cls = "field-hint status-success";

  if (!v.isPositiveInt(nodeCount, 3)) {
    return ["node_count doit etre un entier >= 3", "field-hint status-error"];
  }
  if (!v.isPositiveInt(seed, 0)) {
    return ["seed doit etre un entier >= 0", "field-hint status-error"];
  }
  if (!v.isFloat(sigma, 0, null, true)) {
    return ["dynamic_sigma doit etre > 0", "field-hint status-error"];
  }
  if (!v.isFloat(meanRev, 0, 1, true)) {
    return ["dynamic_mean_reversion_strength doit etre dans ]0,1]", "field-hint status-error"];
  }
  if (!v.isFloat(maxMult, 1, null, false)) {
    return ["dynamic_max_multiplier doit etre >= 1", "field-hint status-error"];
  }
  if (!v.isFloat(forbidProb, 0, 1, false)) {
    return ["dynamic_forbid_probability doit etre dans [0,1]", "field-hint status-error"];
  }
  if (!v.isFloat(restoreProb, 0, 1, false)) {
    return ["dynamic_restore_probability doit etre dans [0,1]", "field-hint status-error"];
  }
  if (!v.isFloat(maxDisabled, 0, 1, false)) {
    return ["dynamic_max_disabled_ratio doit etre dans [0,1]", "field-hint status-error"];
  }

  return [msg, cls];
};
