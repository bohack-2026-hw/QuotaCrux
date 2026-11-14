window.__ModuleLoader__.load({
  id: '@local/quotacrux-dsh',
  factory(require) {
    const React = require('react');
    const h = React.createElement;
    const dictionaries = {
      zh: { engine: '枢决接管', local: '本地', remote: '远程', validation: '候选验证', reuse: '经验复验', times: '次',
        details: '远程原因与具体工作见本轮工具调用记录', saved: '上次真实运行' },
      en: { engine: 'QuotaCrux', local: 'Local', remote: 'Remote', validation: 'Validation', reuse: 'Reuse checks', times: 'calls',
        details: 'Remote reasons and contributions are in the tool calls', saved: 'Previous live run' },
    };
    function StatusLine(props) {
      const state = props.useProjection('quotacruxLive');
      if (!state?.enabled) return null;
      const text = `${props.t(state.read_saved ? 'saved' : 'engine')} · ${props.t('local')} ${state.local} ${props.t('times')} · ${props.t('remote')} ${state.remote}/${state.remote_limit} ${props.t('times')} · ${props.t('validation')} ${state.validations} · ${props.t('reuse')} ${state.reused} · ${state.headline}`;
      return h('div', {
        role: 'status', 'aria-live': 'polite', title: `${text}。${props.t('details')}`,
        style: { color: 'var(--dsw-alias-label-tertiary)', fontSize: '12px', lineHeight: '20px',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '100%', padding: '4px 0' },
      }, text);
    }
    return {
      inject: ['slots', 'locale'],
      apply(ctx) {
        ctx.effect(() => ctx.locale.register('quotacrux', dictionaries));
        ctx.slots.inject('conversation.composer.dock', () => ctx.slots.register({
          name: 'conversation.composer.dock', id: 'quotacrux-status-line', locale: 'quotacrux', order: 5,
        }, StatusLine));
      },
    };
  },
});
