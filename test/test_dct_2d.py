#!/usr/bin/env python
# coding=utf-8

import numpy as np

import pytest
import myhdl
from myhdl import (StopSimulation, block, Signal, ResetSignal, intbv,
                   delay, instance, always_comb, always_seq)
from myhdl.conversion import verify

from jpegenc.subblocks.common import (input_interface, outputs_2d, assign,
                                      assign_array)

from jpegenc.subblocks.dct import dct_2d
from jpegenc.subblocks.dct.dct_2d import dct_2d_transformation
from jpegenc.testing import sim_available, run_testbench
from jpegenc.testing import clock_driver, reset_on_start, pulse_reset

simsok = sim_available('ghdl')
"""default simulator"""
verify.simulator = "ghdl"


class InputsAndOutputs(object):

    """Inputs and Outputs Construction Class

    This class is used to create the inputs and the derive the ouputs from the
    software reference of the 2d-dct. Each element in the input list is fed in the
    test module and the outputs of the module are compared with the elements in the
    outputs list. These list are converted to tuples and used as ROMs in the
    convertible testbench

    """

    def __init__(self, samples, N):
        self.N = N
        self.inputs = []
        self.outputs = []
        self.samples = samples

    def initialize(self):
        """Initialize the inputs and outputs lists"""
        dct_obj = dct_2d_transformation(self.N)
        for i in range(self.samples):
            random_matrix = self.random_matrix_8_8()
            self.inputs.append(random_matrix)
            dct_result = dct_obj.dct_2d_transformation(random_matrix)
            self.outputs.append(dct_result)

    def random_matrix_8_8(self):
        """Create a random NxN matrix with values from 0 to 255"""
        random_matrix = np.random.rand(self.N, self.N)
        random_matrix = np.rint(255*random_matrix)
        random_matrix = random_matrix.astype(int)
        random_matrix = random_matrix.tolist()
        return random_matrix

    def get_rom_tables(self):
        """Convert the lists to tuples"""
        a, b = [[] for _ in range(2)]
        for i in self.inputs:
            for j in i:
                for k in j:
                  a.append(k)
        for i in self.outputs:
            for j in i:
                for k in j:
                    b.append(k)
        inputs_rom = tuple(a)
        expected_outputs_rom = tuple(b)
        return inputs_rom, expected_outputs_rom


def out_print(expected_outputs, actual_outputs, N):
    """Helper function for better printing of the results"""
    print("Expected Outputs ===> ")
    print(expected_outputs)
    print("Actual Outputs   ===> ")
    a = []
    for i in range(N):
        b = []
        for j in range(N):
            b.append(int(actual_outputs[i*N + j]))
        a.append(b)
    print(a)
    print("-"*40)


def test_dct_2d():
    """2D-DCT MyHDL Test

    In this test is verified the correct behavior of the 2d-dct module
    """

    samples, fract_bits, output_bits, stage_1_prec, N = 5, 14, 10, 10, 8

    clock = Signal(bool(0))
    reset = ResetSignal(1, active=True, async=True)

    inputs = input_interface()
    outputs = outputs_2d(output_bits, N)

    in_out_data = InputsAndOutputs(samples, N)
    in_out_data.initialize()

    @myhdl.block
    def bench_dct_2d():
        tdut = dct_2d(inputs, outputs, clock, reset, fract_bits, stage_1_prec,
                      output_bits, N)
        tbclock = clock_driver(clock)

        @instance
        def tbstim():
            yield pulse_reset(reset, clock)
            inputs.data_valid.next = True

            for i in range(samples):
                for j in in_out_data.inputs[i]:
                    for k in j:
                        inputs.data_in.next = k
                        yield clock.posedge

        @instance
        def monitor():
            outputs_count = 0
            while outputs_count != samples:
                yield clock.posedge
                yield delay(1)
                if outputs.data_valid:
                    out_print(in_out_data.outputs[outputs_count],
                              outputs.out_sigs, N)
                    outputs_count += 1
            raise StopSimulation

        return tdut, tbclock, tbstim, monitor

    run_testbench(bench_dct_2d)


@pytest.mark.skipif(not simsok, reason="missing installed simulator")
def test_dct_2d_conversion():
    """Convertible 2D-DCT Test

    This is the convertible testbench which ensures that the overall
    design is convertible and verified for its correct behavior"""

    samples, fract_bits, output_bits, stage_1_prec, N = 5, 14, 10, 10, 8

    clock = Signal(bool(0))
    reset = ResetSignal(1, active=True, async=True)

    inputs = input_interface()
    outputs = outputs_2d(output_bits, N)

    in_out_data = InputsAndOutputs(samples, N)
    in_out_data.initialize()

    inputs_rom, expected_outputs_rom = in_out_data.get_rom_tables()

    @myhdl.block
    def bench_dct_2d():
        tdut = dct_2d(inputs, outputs, clock, reset, fract_bits, output_bits,
                      stage_1_prec, N)
        tbclk = clock_driver(clock)
        tbrst = reset_on_start(reset, clock)

        print_sig = [Signal(intbv(0, min=-2**output_bits, max=2**output_bits))
                     for _ in range(N**2)]
        print_sig_1 = [Signal(intbv(0, min=-2**output_bits, max=2**output_bits))
                       for _ in range(N**2)]

        @instance
        def tbstim():
            yield reset.negedge
            inputs.data_valid.next =True

            for i in range(samples * (N**2)):
                inputs.data_in.next = inputs_rom[i]
                yield clock.posedge

        print_assign = assign_array(print_sig_1, outputs.out_sigs)

        @instance
        def monitor():
            outputs_count = 0
            while outputs_count != samples:
                yield clock.posedge
                if outputs.data_valid:
                    for i in range(N**2):
                        print_sig[i].next = expected_outputs_rom[outputs_count * (N**2) + i]

                    yield delay(1)
                    print("Expected Outputs")
                    for i in range(N**2):
                        print("%d " % print_sig[i])

                    print("Actual Outputs")
                    for i in range(N**2):
                        print("%d " % print_sig_1[i])
                    print("------------------------------")
                    outputs_count += 1

            raise StopSimulation

        return tdut, tbclk, tbstim, monitor, tbrst, print_assign

    assert bench_dct_2d().verify_convert() == 0

if __name__ == '__main__':
    test_dct_2d()
    test_dct_2d_conversion()
