const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

test('every recovery category and policy source has Chinese and English copy', () => {
  const window = { localStorage: { getItem() {}, setItem() {} } };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../../demo-ui/dist/i18n.js'), 'utf8'), {
    window, document: { documentElement: {} }, Intl,
  });
  const codes = [
    'repository_missing', 'repository_not_git', 'repository_root', 'base_unresolved',
    'repository_dirty', 'repository_check_failed', 'policy_invalid', 'policy_conflict',
    'verification_missing', 'write_scope_missing', 'artifact_integrity', 'unexpected_error',
  ];
  const keys = [
    ...codes.flatMap(code => ['title', 'copy'].map(part => `recovery_${code}_${part}`)),
    ...['demo_fixture', 'repository_config', 'operator_config', 'deterministic_discovery'].map(source => `policySource_${source}`),
    'setupTitle', 'setupNoTests', 'recoveryBeforeRun', 'recoveryEditRequest',
  ];
  for (const key of keys) {
    window.PRGuardLocale.setLanguage('zh');
    const zh = window.PRGuardLocale.t(key);
    window.PRGuardLocale.setLanguage('en');
    const en = window.PRGuardLocale.t(key);
    assert.notEqual(zh, key);
    assert.notEqual(en, key);
    assert.notEqual(zh, en, key + ' must not fall back to untranslated English');
  }
});
