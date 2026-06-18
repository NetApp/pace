export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'body-max-line-length': [0, 'always'],
    'footer-max-line-length': [0, 'always'],
    'subject-case': [0, 'always'],
    'scope-enum': [
      2,
      'always',
      [
        'ansible',
        'ci',
        'deps',
        'docs',
        'go',
        'python',
        'terraform',
      ],
    ],
    'type-enum': [
      2,
      'always',
      [
        'build',
        'chore',
        'ci',
        'doc',
        'feat',
        'fix',
        'perf',
        'refactor',
        'revert',
        'style',
        'test',
      ],
    ],
  },
};
