"""격리 실험 전용 유한 예산. 제품 설정·DB packet 한도와 독립적이다."""
from dataclasses import dataclass

MIB = 1024**2


@dataclass(frozen=True)
class ProbeBudget:
    profile: str
    runner_hard_mib: int
    runner_soft_mib: int
    temp_soft_mib: int
    db_data_mib: int
    disk_start_mib: int
    disk_growth_mib: int
    db_hard_mib: int = 512
    db_soft_mib: int = 440
    host_reserve_mib: int = 700
    collector_reserve_mib: int = 512
    disk_reserve_mib: int = 4096

    @classmethod
    def from_profile(cls, name):
        if type(name) is not str:
            raise ValueError('BUDGET_PROFILE_REQUIRED')
        if name == 'legacy':
            return cls(name, 1280, 1100, 512, 1024, 6144, 2048)
        if name == 'coarse-1200-384m':
            return cls(name, 2176, 1900, 896, 2048, 8192, 3072)
        raise ValueError('BUDGET_UNKNOWN_PROFILE')

    def validate_experiment(self, output_bytes, duration_ms, timeout_sec):
        if any(type(v) is not int for v in (output_bytes, duration_ms, timeout_sec)):
            raise ValueError('BUDGET_FINITE_INTEGERS_REQUIRED')
        if self.profile == 'legacy':
            valid = (50331648 <= output_bytes <= 256*MIB and 240000 <= duration_ms <= 1200000
                     and 900 <= timeout_sec <= 3600)
        else:
            # 한쪽 한도만 올리는 조합은 허용하지 않는다.
            valid = (output_bytes, duration_ms, timeout_sec) == (384*MIB, 1200000, 3000)
        if not valid:
            raise ValueError('BUDGET_COORDINATED_EXPERIMENT_REQUIRED')

    @property
    def host_start_bytes(self):
        return (self.runner_hard_mib + self.db_hard_mib + self.host_reserve_mib + self.collector_reserve_mib)*MIB

    def host_timeout_sec(self, runner_timeout):
        if type(runner_timeout) is not int or not 900 <= runner_timeout <= 3600:
            raise ValueError('BUDGET_TIMEOUT_INVALID')
        return runner_timeout + 30

    def requirements(self, output_cap, search_candidate):
        if any(type(v) is not int or v <= 0 for v in (output_cap, search_candidate)):
            raise ValueError('BUDGET_FINITE_BYTES_REQUIRED')
        # concat: part/remux+final; Search: detached+copy+output (phase 중첩 아님).
        # 메모리4N은 bytes/파일 cache 후보이고240MiB는 tool/probe/runtime 예비다.
        return {'temp_candidate_bytes': 2*output_cap + search_candidate,
            'runner_candidate_bytes': 4*output_cap + 240*MIB,
            'db_growth_candidate_bytes': 3*output_cap,
            'disk_growth_candidate_bytes': 5*output_cap + search_candidate + 64*MIB}

    def preflight(self, *, available_ram, c_free, disk_growth_used, db_data, output_cap, search_candidate):
        observed = (available_ram, c_free, disk_growth_used, db_data)
        if any(type(v) is not int or v < 0 for v in observed):
            raise ValueError('BUDGET_OBSERVATION_INVALID')
        needed = self.requirements(output_cap, search_candidate)
        checks = [
            (available_ram >= self.host_start_bytes, 'HOST_RAM'),
            (c_free >= self.disk_start_mib*MIB, 'HOST_DISK'),
            (needed['temp_candidate_bytes'] < self.temp_soft_mib*MIB, 'TEMP'),
            (needed['runner_candidate_bytes'] < self.runner_soft_mib*MIB, 'RUNNER'),
            (db_data + needed['db_growth_candidate_bytes'] < self.db_data_mib*MIB, 'DB_DATA'),
            (disk_growth_used + needed['disk_growth_candidate_bytes'] <= self.disk_growth_mib*MIB, 'DISK_GROWTH'),
            (c_free - needed['disk_growth_candidate_bytes'] >= self.disk_reserve_mib*MIB, 'DISK_RESERVE'),
        ]
        for valid, code in checks:
            if not valid:
                raise ValueError('BUDGET_' + code + '_STOP')
        return {'status': 'PASS', **needed, 'available_ram_bytes': available_ram, 'C_free_bytes': c_free,
            'disk_growth_used_bytes': disk_growth_used, 'db_data_bytes': db_data,
            'host_start_bytes': self.host_start_bytes}
