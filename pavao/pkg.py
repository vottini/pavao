
import os
import sys
import json
import hashlib
import shutil
import tarfile
import tempfile
import argparse
import subprocess
import urllib.request
import urllib.error

PACKAGES_FILE = "pavao_packages.json"
DEFAULT_FOUNDATION = "foundation"
DEFAULT_MODULES = "modules"

#-------------------------------------------------------------------------------

def _load_packages():
	if not os.path.exists(PACKAGES_FILE):
		return {}
	with open(PACKAGES_FILE) as f:
		return json.load(f)


def _save_packages(packages):
	with open(PACKAGES_FILE, 'w') as f:
		json.dump(packages, f, indent=2)
		f.write('\n')


def _parse_ref(ref):
	if '@' not in ref:
		print(f"error: tag required — use {ref}@<tag>")
		sys.exit(1)

	repo, tag = ref.rsplit('@', 1)
	repo = repo.strip('/')

	# accept https://github.com/... or github.com/... or owner/repo
	if '://' in repo:
		repo = repo.split('://', 1)[1]

	segments = [s for s in repo.split('/') if s and s != 'github.com']
	if len(segments) < 2:
		print(f"error: expected owner/repo, got '{repo}'")
		sys.exit(1)

	owner, repo_name = segments[-2], segments[-1]
	canonical = f"github.com/{owner}/{repo_name}"

	short = repo_name[len('pavao-'):] if repo_name.startswith('pavao-') else repo_name
	return canonical, owner, repo_name, tag, short


def _archive_url(owner, repo_name, tag):
	return f"https://github.com/{owner}/{repo_name}/archive/refs/tags/{tag}.tar.gz"


def _download(url):
	print(f"  fetching {url}")
	try:
		with urllib.request.urlopen(url) as r:
			return r.read()
	except urllib.error.HTTPError as e:
		print(f"error: HTTP {e.code} — {url}")
		sys.exit(1)
	except urllib.error.URLError as e:
		print(f"error: {e.reason}")
		sys.exit(1)


def _sha256(data):
	return "sha256:" + hashlib.sha256(data).hexdigest()


def _check_requirements(req_file):
	try:
		from packaging.requirements import Requirement
		from packaging.version import Version
		from packaging.specifiers import SpecifierSet
		import importlib.metadata as meta
	except ImportError:
		return []

	conflicts = []
	with open(req_file) as f:
		for line in f:
			line = line.strip()
			if not line or line.startswith('#'):
				continue
			try:
				req = Requirement(line)
				try:
					installed_ver = Version(meta.version(req.name))
					lower_bounds = SpecifierSet(
						','.join(str(s) for s in req.specifier if s.operator in ('>=', '>')))
					if lower_bounds and not lower_bounds.contains(installed_ver, prereleases=True):
						conflicts.append((str(req), str(installed_ver)))
				except meta.PackageNotFoundError:
					pass
			except Exception:
				pass

	return conflicts


def _install(data, short, foundation_dir, modules_dir, force=False):
	with tempfile.TemporaryDirectory() as tmp:
		tarball = os.path.join(tmp, 'pkg.tar.gz')
		with open(tarball, 'wb') as f:
			f.write(data)

		with tarfile.open(tarball, 'r:gz') as tar:
			members = [
				m for m in tar.getmembers()
				if not os.path.isabs(m.name) and '..' not in m.name.split('/')
			]
			tar.extractall(tmp, members=members)

		entries = [
			e for e in os.listdir(tmp)
			if os.path.isdir(os.path.join(tmp, e)) and e != '__MACOSX'
		]
		if not entries:
			print("error: archive contained no directory")
			sys.exit(1)

		root = os.path.join(tmp, entries[0])
		installed = False

		for src_name, dst_base in [('foundation', foundation_dir), ('modules', modules_dir)]:
			src = os.path.join(root, src_name)
			if not os.path.isdir(src):
				continue

			dst = os.path.join(dst_base, short)
			if os.path.exists(dst):
				shutil.rmtree(dst)

			os.makedirs(dst_base, exist_ok=True)
			shutil.copytree(src, dst)
			print(f"  {src_name}/ → {dst}/")
			installed = True

		if not installed:
			print(f"  warning: no foundation/ or modules/ found in package")

		req_file = os.path.join(root, 'requirements.txt')
		if os.path.isfile(req_file):
			conflicts = _check_requirements(req_file)
			if conflicts and not force:
				print(f"  dependency conflict — the extension requires versions that differ from what is installed:")
				for req, installed_ver in conflicts:
					print(f"    {req}  (installed: {installed_ver})")
				print(f"  aborting — use --force to install anyway")
				sys.exit(1)

			print(f"  installing requirements...")
			result = subprocess.run(
				[sys.executable, '-m', 'pip', 'install', '-r', req_file],
				capture_output=True, text=True)
			if result.returncode != 0:
				print(f"  warning: pip exited with code {result.returncode}")
				print(result.stderr.strip())
			else:
				print(f"  requirements installed")


def _remove_dirs(short, foundation_dir, modules_dir):
	for base in [foundation_dir, modules_dir]:
		target = os.path.join(base, short)
		if os.path.isdir(target):
			shutil.rmtree(target)
			print(f"  removed {target}/")


def _gitignore_entries(short, foundation_dir, modules_dir):
	return [
		os.path.join(foundation_dir, short) + '/',
		os.path.join(modules_dir, short) + '/',
	]


def _add_to_gitignore(short, foundation_dir, modules_dir):
	entries = _gitignore_entries(short, foundation_dir, modules_dir)
	gitignore = '.gitignore'

	content = ''
	if os.path.isfile(gitignore):
		with open(gitignore) as f:
			content = f.read()

	existing = {line.rstrip('\n') for line in content.splitlines()}
	to_add = [e for e in entries if e not in existing]
	if not to_add:
		return

	with open(gitignore, 'a') as f:
		if content and not content.endswith('\n'):
			f.write('\n')
		for entry in to_add:
			f.write(entry + '\n')
			print(f"  .gitignore ← {entry}")


def _remove_from_gitignore(short, foundation_dir, modules_dir):
	entries = set(_gitignore_entries(short, foundation_dir, modules_dir))
	gitignore = '.gitignore'

	if not os.path.isfile(gitignore):
		return

	with open(gitignore) as f:
		lines = f.readlines()

	kept = [l for l in lines if l.rstrip('\n') not in entries]
	if len(kept) == len(lines):
		return

	with open(gitignore, 'w') as f:
		f.writelines(kept)
	print(f"  .gitignore — removed {short} entries")


def _resolve_name(packages, name_arg):
	for key in packages:
		short = key[len('pavao-'):] if key.startswith('pavao-') else key
		if key == name_arg or short == name_arg:
			return key
	return None

#-------------------------------------------------------------------------------

def cmd_add(args):
	canonical, owner, repo_name, tag, short = _parse_ref(args.package)
	packages = _load_packages()

	if repo_name in packages:
		print(f"'{repo_name}' is already added — use 'update' to change version")
		sys.exit(1)

	data = _download(_archive_url(owner, repo_name, tag))
	hash_val = _sha256(data)

	_install(data, short, args.foundation, args.modules, args.force)
	_add_to_gitignore(short, args.foundation, args.modules)
	packages[repo_name] = {'repo': canonical, 'tag': tag, 'hash': hash_val}
	_save_packages(packages)
	print(f"added {repo_name}@{tag}")


def cmd_update(args):
	packages = _load_packages()
	ref = args.package

	new_tag = None
	if '@' in ref:
		name_arg, new_tag = ref.rsplit('@', 1)
	else:
		name_arg = ref

	entry_name = _resolve_name(packages, name_arg)
	if entry_name is None:
		print(f"'{name_arg}' not found in {PACKAGES_FILE}")
		sys.exit(1)

	entry = packages[entry_name]
	tag = new_tag or entry['tag']
	short = entry_name[len('pavao-'):] if entry_name.startswith('pavao-') else entry_name

	canonical = entry['repo']
	segments = [s for s in canonical.split('/') if s and s != 'github.com']
	owner, repo_name = segments[-2], segments[-1]

	data = _download(_archive_url(owner, repo_name, tag))
	hash_val = _sha256(data)

	_install(data, short, args.foundation, args.modules, args.force)
	entry['tag'] = tag
	entry['hash'] = hash_val
	_save_packages(packages)
	print(f"updated {entry_name}@{tag}")


def cmd_remove(args):
	packages = _load_packages()
	entry_name = _resolve_name(packages, args.package)

	if entry_name is None:
		print(f"'{args.package}' not found in {PACKAGES_FILE}")
		sys.exit(1)

	short = entry_name[len('pavao-'):] if entry_name.startswith('pavao-') else entry_name
	_remove_dirs(short, args.foundation, args.modules)
	_remove_from_gitignore(short, args.foundation, args.modules)
	del packages[entry_name]
	_save_packages(packages)
	print(f"removed {entry_name}")


def cmd_sync(args):
	packages = _load_packages()
	if not packages:
		print(f"nothing to sync — {PACKAGES_FILE} is empty")
		return

	failed = False
	for name, entry in packages.items():
		short = name[len('pavao-'):] if name.startswith('pavao-') else name
		segments = [s for s in entry['repo'].split('/') if s and s != 'github.com']
		owner, repo_name = segments[-2], segments[-1]

		print(f"syncing {name}@{entry['tag']}...")
		data = _download(_archive_url(owner, repo_name, entry['tag']))
		actual = _sha256(data)

		if actual != entry['hash']:
			print(f"  hash mismatch for {name}!")
			print(f"    expected: {entry['hash']}")
			print(f"    got:      {actual}")
			print(f"  the tag may have been force-pushed — aborting")
			failed = True
			break

		_install(data, short, args.foundation, args.modules, args.force)

	if failed:
		sys.exit(1)


def cmd_list(_args):
	packages = _load_packages()
	if not packages:
		print(f"no packages in {PACKAGES_FILE}")
		return
	for name, entry in packages.items():
		print(f"  {name}@{entry['tag']}  ({entry['repo']})")

#-------------------------------------------------------------------------------

def main():
	parser = argparse.ArgumentParser(
		prog='pavao-pkg',
		description='manage pavao extension packages')

	parser.add_argument('--foundation', default=DEFAULT_FOUNDATION, metavar='DIR',
		help=f"foundation directory (default: {DEFAULT_FOUNDATION})")
	parser.add_argument('--modules', default=DEFAULT_MODULES, metavar='DIR',
		help=f"modules directory (default: {DEFAULT_MODULES})")

	sub = parser.add_subparsers(dest='command', required=True)

	p = sub.add_parser('add', help='add a package pinned to a tag')
	p.add_argument('package', help='github.com/owner/repo@tag')
	p.add_argument('--force', action='store_true', help='install despite dependency conflicts')
	p.set_defaults(func=cmd_add)

	p = sub.add_parser('update', help='update a package to a new tag')
	p.add_argument('package', help='name[@tag] — omit tag to re-fetch current version')
	p.add_argument('--force', action='store_true', help='install despite dependency conflicts')
	p.set_defaults(func=cmd_update)

	p = sub.add_parser('remove', help='remove a package')
	p.add_argument('package', help='package name (pavao-auth or auth)')
	p.set_defaults(func=cmd_remove)

	p = sub.add_parser('sync', help='pull all packages and verify hashes')
	p.add_argument('--force', action='store_true', help='install despite dependency conflicts')
	p.set_defaults(func=cmd_sync)

	p = sub.add_parser('list', help='list installed packages')
	p.set_defaults(func=cmd_list)

	args = parser.parse_args()
	args.func(args)


if __name__ == '__main__':
	main()
