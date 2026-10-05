// Execute the actual inline workflow scripts against controlled service boundaries.
// This is an integration fixture, not a claim to run GitHub's scheduler or OIDC.
let input = '';
for await (const chunk of process.stdin) input += chunk;
const fixture = JSON.parse(input);
const { caller, hosted, mode, faults = {} } = fixture;
const steps = {}, operations = [], calls = [], warnings = [], logs = [];
const masks = [];
const oidc = 'synthetic_oidc_value';
const reviewer = 'ghu_SYNTHETIC_PERSONAL_TOKEN';
const env = {
  ...process.env, AUTOMATED_REVIEW: mode,
  BROKER_URL: faults.brokerMissing ? '' : 'https://broker.example/hosted/authority',
  BROKER_AUDIENCE: faults.audienceMissing ? '' : 'shoal-hosted-review',
  REPOSITORY_ID: '17', OWNER_ID: '42', WORKFLOW_REF: 'owner/station/.github/workflows/reviewer-summary.yml@refs/heads/main',
  WORKFLOW_SHA: 'a'.repeat(40), GITHUB_RUN_ATTEMPT: '1'
};
if (faults.brokerUrl) env.BROKER_URL = faults.brokerUrl;
const inputs = { automated_review: mode };
const github = { token: 'synthetic_workflow_token', repository: 'owner/station', workspace: '/station', sha: 'a'.repeat(40) };
Object.assign(github, { repository_id: env.REPOSITORY_ID, repository_owner_id: env.OWNER_ID,
  workflow_ref: env.WORKFLOW_REF, workflow_sha: env.WORKFLOW_SHA });
const vars = { SHOAL_HOSTED_BROKER_URL: env.BROKER_URL, SHOAL_HOSTED_BROKER_AUDIENCE: env.BROKER_AUDIENCE };
const context = { runId: 1234 };
const core = {
  setOutput: (key, value) => { steps[current].outputs[key] = String(value); },
  setSecret: value => masks.push(value),
  warning: value => warnings.push(value),
  info: value => logs.push(value),
  getIDToken: async audience => {
    calls.push({ kind: 'oidc', audience });
    if (faults.oidc) throw new Error('SECRET upstream diagnostic');
    return oidc;
  }
};
const fetch = async (url, options) => {
  calls.push({ kind: 'broker', url: String(url), redirect: options.redirect, body: JSON.parse(options.body) });
  if (options.headers.Authorization !== `Bearer ${oidc}`) throw new Error('Missing OIDC');
  if (faults.brokerNetwork) throw new Error('SECRET external exception');
  const result = {
    formatVersion: 1, repositoryId: '17', reviewerId: '42', reviewerToken: reviewer,
    expiresAt: new Date(Date.now() + 3600000).toISOString(), ...faults.brokerResult
  };
  const raw = faults.brokerMalformed ? 'SECRET not json' : faults.brokerOversized ? 'x'.repeat(9000) : JSON.stringify(result);
  return {
    ok: !faults.brokerDenied,
    body: new ReadableStream({ start(controller) { controller.enqueue(Buffer.from(raw)); controller.close(); } })
  };
};
const evaluate = expression => {
  if (typeof expression !== 'string' || !expression.startsWith('${{')) return expression;
  return Function('steps', 'inputs', 'github', 'vars', 'always', `return (${expression.slice(3, -2)});`)(steps, inputs, github, vars, () => true);
};
let current;
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
for (const step of hosted.jobs.hosted.steps) {
  current = step.id;
  steps[current] = { outcome: 'skipped', outputs: {} };
  if (step.if && !evaluate(step.if)) continue;
  steps[current].outcome = 'success';
  try {
    if (current === 'checkout') {
      calls.push({ kind: 'checkout', ref: evaluate(step.with.ref), persistCredentials: step.with['persist-credentials'] });
      if (faults.checkout) throw new Error('checkout failed');
    } else if (['review', 're_review'].includes(current)) {
      const operation = step.with.operation;
      operations.push(operation);
      const credentialRoles = Object.fromEntries(['copilot_token', 'read_token', 'lifecycle_token', 'reviewer_token'].map(k => [k, evaluate(step.with[k])]));
      if (credentialRoles.reviewer_token !== reviewer || credentialRoles.lifecycle_token !== reviewer ||
          credentialRoles.copilot_token === reviewer || credentialRoles.read_token === reviewer) throw new Error('authority crossover');
      const fault = faults[operation] || {};
      if (fault.infrastructure) throw new Error('host infrastructure failed');
      const result = {
        formatVersion: 1, operation, runtimeSource: 'b'.repeat(40),
        runtime: { status: fault.status || 'COMPLETED', effectAttempts: 0, faults: [] },
        failures: fault.failures || [], stopSemanticWork: fault.stop ?? false
      };
      steps[current].outputs = {
        result: fault.malformed ? 'SECRET malformed' : JSON.stringify(result),
        status: fault.outputStatus || result.runtime.status,
        stop_semantic_work: fault.outputStop || String(result.stopSemanticWork)
      };
    } else {
      const previous = process.env;
      process.env = { ...env, ...Object.fromEntries(Object.entries(step.env || {}).map(([k,v]) => [k, String(evaluate(v) ?? '')])) };
      try { await new AsyncFunction('core', 'context', 'fetch', step.with.script)(core, context, fetch); }
      finally { process.env = previous; }
    }
  } catch {
    steps[current].outcome = 'failure';
    if (step['continue-on-error'] !== 'true') {
      // Remaining always() diagnostics still execute after an infrastructure failure.
      faults.scriptFailure = true;
    }
  }
}
// Credential values are never returned by the fixture's observable output.
const output = { operations, calls, warnings, logs, result: steps.result.outputs,
  authority: { ready: steps.authority.outputs.ready, code: steps.authority.outputs.code },
  reviewGate: steps.review_gate.outputs, outcomes: Object.fromEntries(Object.entries(steps).map(([k,v]) => [k,v.outcome])) };
const publishExpression = caller.jobs.publish.if.slice(3, -2);
output.publishAllowed = Function('needs', 'always', `return (${publishExpression});`)(
  { summary: { result: fixture.summaryResult || 'success' } }, () => true);
const text = JSON.stringify(output);
if ([oidc, reviewer, 'SECRET'].some(secret => text.includes(secret))) throw new Error('Credential/diagnostic disclosure');
process.stdout.write(text);
